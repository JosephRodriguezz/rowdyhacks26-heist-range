import {test, before, after} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {randomBytes, randomUUID} from 'node:crypto';
import {mkdtempSync, readFileSync, unlinkSync, rmdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {PGlite} from '@electric-sql/pglite';
import {login, read, resetDatabase, state} from '../src/lib/bank.mjs';
import {AvailabilityLab} from '../src/lib/availability-lab.mjs';
import {createBankRegistry, createDisposableRegistry, validateApproval} from '../integration/registry.mjs';
import {BankAvailabilityAdapter} from '../integration/adapter.mjs';
import {EvidenceLedger, assessRecovery} from '../integration/evidence.mjs';
import {boundedRequest} from '../integration/transport.mjs';

let engine, db;
before(async () => {
  engine = new PGlite(); await engine.waitReady;
  db = {query: async (sql, values) => values ? engine.query(sql, values) : (await engine.exec(sql)).at(-1)};
});
after(async () => { await engine.close(); });
const testConfig = () => ({customerPassword: randomBytes(24).toString('hex'), vaultPassword: randomBytes(24).toString('hex')});
const approvalFor = bankState => ({approvalId: 'fixture-calibration', scope: 'isolated-lab',
  runId: bankState.run_id, scenarioVersion: bankState.scenario_version, baselineEvidenceRefs: ['fixture-baseline'],
  profile: {maxRequests: 24, maxConcurrent: 5, durationMs: 1500, requestTimeoutMs: 500,
    minIntervalMs: 100, probeRequests: 30, controlRequests: 4},
  criteria: {healthMaxMs: 400, ordinaryMaxMs: 400, recoverySamples: 2, baselineMaxAgeMs: 500}});

async function fixture(t, changes = {}) {
  const config = testConfig();
  await resetDatabase(db, config);
  const bankState = await state(db);
  const customer = await login(db, 'customer', config.customerPassword);
  const own = await read(db, 'accounts', customer.token);
  const credentials = {load: randomBytes(32).toString('hex'), probe: randomBytes(32).toString('hex'),
    executor: randomBytes(32).toString('hex'), ordinary: {session: customer.token,
      ownerId: own.body.accounts[0].owner_id, accountIds: own.body.accounts.map(a => a.account_id)}};
  const approval = approvalFor(bankState);
  Object.assign(approval.profile, changes.profile);
  Object.assign(approval.criteria, changes.criteria);
  const lab = new AvailabilityLab({enabled: true, approval: {approvalId: approval.approvalId,
    runId: approval.runId, scenarioVersion: approval.scenarioVersion}, credentials,
    profile: {maxRequests: 24, maxConcurrent: 3, durationMs: 1800, workMs: 120,
      degradedAt: 2, mitigationTtlMs: 1500, ...changes.labProfile}});
  const modes = {};
  let origin;
  const server = createServer(async (request, response) => {
    const reply = (status, body) => {
      response.writeHead(status, {'Content-Type': 'application/json'});
      response.end(JSON.stringify(body));
    };
    try {
      if (request.url === '/api/health') {
        if (modes.health === 'redirect') { response.writeHead(302, {Location: 'https://outside.invalid/private'}); response.end(); return; }
        if (modes.health === 'large') { reply(200, {padding: 'x'.repeat(20000)}); return; }
        if (modes.health === 'hang') return;
        reply(200, {status: 'ready', target_id: modes.health === 'identity' ? 'bank-local' : 'bank-lab', ...await state(db)});
        return;
      }
      if (request.url === '/api/accounts') {
        if (modes.ordinary === 'denied') { reply(403, {error: 'Denied'}); return; }
        const token = request.headers.cookie?.match(/^bank_session=([a-f0-9]{64})$/)?.[1];
        const result = await read(db, 'accounts', token);
        if (modes.ordinary === 'malformed') result.body.accounts = [null];
        reply(result.status, result.body); return;
      }
      const operation = request.url?.match(/^\/api\/availability\/(status|work|control)$/)?.[1];
      if (!operation) { reply(404, {error: 'Not found'}); return; }
      const authorization = request.headers.authorization;
      const denied = lab.authorize({method: request.method, operation, authorization});
      if (denied) { reply(denied.status, denied.body); return; }
      let input = {};
      if (request.method === 'POST') {
        if (request.headers.origin !== origin) { reply(403, {error: 'Origin rejected'}); return; }
        let text = '';
        for await (const chunk of request) {
          text += chunk.toString();
          if (text.length > 4096) { reply(413, {error: 'Too large'}); return; }
        }
        input = JSON.parse(text);
      }
      if (operation === 'work' && modes.work === 'hang') return;
      const result = await lab.handle({method: request.method, operation, authorization, input, bankState: await state(db),
        expectedExerciseId: request.headers['x-bank-exercise']});
      if (operation === 'work' && modes.work === 'identity') result.body.target_id = 'bank-local';
      reply(result.status, result.body);
    } catch { if (!response.headersSent) reply(503, {error: 'Fixture unavailable'}); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = `http://127.0.0.1:${server.address().port}`;
  const registry = createDisposableRegistry(server, approval);
  const directory = changes.persist ? mkdtempSync(join(tmpdir(), 'rowdy-availability-')) : undefined;
  const sessionId = `fixture-${randomUUID()}`;
  const ledger = new EvidenceLedger({sessionId, targetId: 'availability-fixture', sourceMode: 'fixture', directory});
  const dispatches = [];
  let activeHttp = 0, peakHttp = 0;
  const transport = async args => {
    dispatches.push({path: args.path, started: performance.now()});
    activeHttp++; peakHttp = Math.max(peakHttp, activeHttp);
    try { return await boundedRequest(args); } finally { activeHttp--; }
  };
  const adapter = new BankAvailabilityAdapter({registry, credentials, ledger,
    approvedDefenseIds: ['fixture-limit'], transport});
  t.after(async () => {
    if (adapter.running()) await adapter.stop();
    const current = await lab.handle({method: 'GET', operation: 'status', authorization: `Bearer ${credentials.probe}`, bankState});
    await lab.handle({method: 'POST', operation: 'control', authorization: `Bearer ${credentials.executor}`,
      input: {action: 'stop'}, bankState, expectedExerciseId: current.body.exercise_id});
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    ledger.close();
    if (directory) { unlinkSync(join(directory, `${sessionId}.jsonl`)); rmdirSync(directory); }
  });
  return {adapter, registry, ledger, approval, lab, bankState, credentials, server, modes, dispatches,
    config, journal: directory && join(directory, `${sessionId}.jsonl`), peakHttp: () => peakHttp};
}
async function baseline(adapter) {
  for (const kind of ['status', 'health', 'ordinary']) assert.equal((await adapter.observe(kind)).data.status, 'available');
}
async function degradation(adapter) {
  for (let attempt = 0; attempt < 10; attempt++) {
    const event = await adapter.observe('status');
    if (event.data.status === 'degraded') return event;
    await delay(10);
  }
  assert.fail('Disposable capacity did not measurably degrade');
}
async function controlLab(f, input) {
  const bankState = await state(db);
  const snapshot = await f.lab.handle({method: 'GET', operation: 'status', authorization: `Bearer ${f.credentials.probe}`, bankState});
  return f.lab.handle({method: 'POST', operation: 'control', authorization: `Bearer ${f.credentials.executor}`,
    input, bankState, expectedExerciseId: snapshot.body.exercise_id});
}
async function continuingWork(f, afterSequence, newDispatch = false) {
  for (let attempt = 0; attempt < 40; attempt++) {
    const entries = f.ledger.entries();
    const outcome = entries.find(e => e.event_type === 'availability.work_observed' &&
      e.sequence > afterSequence && ['completed', 'shed'].includes(e.data.status) && (!newDispatch ||
        entries.some(start => start.event_type === 'availability.work_started' &&
          start.data.request_id === e.data.request_id && start.sequence > afterSequence)));
    if (outcome) return outcome;
    await delay(10);
  }
  assert.fail('No continuing validated fixture load request');
}
// Referee-only synthetic replay creates valid envelopes so negative tests exercise
// the evidence rules rather than merely failing hash/sequence validation.
function replay(entries) {
  const first = entries[0];
  const ledger = new EvidenceLedger({sessionId: first.session_id, targetId: first.target_id, sourceMode: first.source_mode});
  for (const entry of entries) ledger.record(entry.event_type, entry.data);
  return ledger.entries();
}

test('canonical bank registration is disabled by default and rejects aliases and arbitrary destinations before transport', () => {
  let sent = 0;
  const registry = createBankRegistry();
  const ledger = new EvidenceLedger({sessionId: 'disabled-bank', targetId: 'bank-lab', sourceMode: 'live'});
  const adapter = new BankAvailabilityAdapter({registry, ledger, transport: async () => { sent++; }});
  assert.equal(adapter.describe().target_id, 'bank-lab');
  assert.equal(adapter.describe().traffic_enabled, false);
  assert.throws(() => registry.resolve('bank-local', 'work'), /Unknown registered target/);
  assert.throws(() => adapter.dispatch({capability: 'availability.load', target_id: 'bank-lab'}), /not approved/);
  assert.throws(() => createBankRegistry({origin: 'https://outside.invalid'}));
  assert.throws(() => createBankRegistry({deployment: 'https://outside.invalid'}));
  assert.throws(() => createDisposableRegistry({address: () => ({address: '127.0.0.1', port: 3000})}, {}));
  assert.equal(sent, 0);
});

test('approval requires scoped measured criteria and rejects nonfinite, excessive, coercible, or mutable profiles', () => {
  const approval = approvalFor({run_id: randomUUID(), scenario_version: 'baseline-v1'});
  for (const key of Object.keys(approval.profile)) {
    for (const value of [NaN, Infinity, true, '1', -1, 0]) {
      assert.throws(() => validateApproval({...approval, profile: {...approval.profile, [key]: value}}));
    }
  }
  assert.throws(() => validateApproval({...approval, baselineEvidenceRefs: []}));
  assert.throws(() => validateApproval({...approval, scope: 'public'}));
  assert.throws(() => validateApproval({...approval, profile: {...approval.profile, maxRequests: 61}}));
  assert.throws(() => validateApproval({...approval, profile: {...approval.profile, maxConcurrent: 13}}));
  const registry = createBankRegistry({approval});
  const disposable = createBankRegistry({deployment: 'disposable-desktop', approval});
  assert.equal(disposable.resolve('bank-lab', 'work').origin, 'http://127.0.0.1:3001');
  assert.equal(disposable.describe().source_mode, 'live');
  assert.throws(() => disposable.resolve('bank-local', 'work'), /Unknown registered target/);
  approval.profile.maxRequests = 10000;
  assert.equal(registry.resolve('bank-lab', 'work').approval.profile.maxRequests, 24);
});

test('Red requests cannot smuggle URL, method, identity, payload, or profile overrides', async t => {
  const f = await fixture(t);
  const initial = f.dispatches.length;
  for (const changes of [{target_id: 'bank-local'}, {url: 'https://outside.invalid'}, {path: '//outside.invalid'},
    {method: 'POST'}, {body: {maxRequests: 10000}}, {identity_ref: 'other-user'}, {session_ref: 'forged'},
    {form_ref: 'forged'}, {profile: {}}, {capability: 'unregistered'}]) {
    assert.throws(() => f.adapter.dispatch({capability: 'start_load_test', target_id: 'availability-fixture', ...changes}));
  }
  assert.throws(() => f.adapter.dispatch({capability: 'start_load_test', target_id: 'availability-fixture'}), /baseline/);
  assert.equal(f.dispatches.length, initial);
});

test('redirects, oversize responses, timeouts, mismatched identity, and malformed accounts stay inconclusive', async t => {
  const f = await fixture(t);
  for (const [mode, error] of [['redirect', 'redirect_rejected'], ['large', 'response_too_large'],
    ['identity', 'identity_mismatch'], ['hang', 'timeout']]) {
    f.modes.health = mode;
    const event = await f.adapter.observe('health');
    assert.equal(event.data.status, 'inconclusive');
    assert.equal(event.data.error, error);
  }
  f.modes.ordinary = 'malformed';
  assert.equal((await f.adapter.observe('ordinary')).data.status, 'inconclusive');
  const text = JSON.stringify(f.ledger.entries());
  for (const secret of [f.credentials.load, f.credentials.probe, f.credentials.executor, f.credentials.ordinary.session]) {
    assert.equal(text.includes(secret), false);
  }
  assert.equal(text.includes('outside.invalid'), false);
  assert.equal(text.includes('balance_cents'), false);
});

test('repeatable disposable slice independently verifies degradation and ordinary access during continuing mitigated load', async t => {
  for (let repetition = 0; repetition < 2; repetition++) {
    await t.test(`isolated repetition ${repetition + 1}`, async child => {
      const f = await fixture(child, {persist: true});
      await baseline(f.adapter);
      const receipt = f.adapter.dispatch({capability: 'start_load_test', target_id: 'availability-fixture',
        path: '/', method: 'GET', body: {}, identity_ref: null, session_ref: null, form_ref: null});
      await degradation(f.adapter);
      // Explicit fixture responder proposes a pre-approved action; this is not Joseph's Blue implementation.
      assert.throws(() => f.adapter.applyDefense('unapproved'), /not approved/);
      const defense = await f.adapter.applyDefense('fixture-limit');
      assert.equal(defense.data.status, 'applied');
      await delay(140); // already admitted bounded work drains; later load is shed
      await continuingWork(f, defense.sequence);
      for (let sample = 0; sample < f.approval.criteria.recoverySamples; sample++) {
        assert.equal(f.adapter.running(), true);
        assert.equal((await f.adapter.observe('status')).data.status, 'available');
        assert.equal((await f.adapter.observe('health')).data.status, 'available');
        assert.equal((await f.adapter.observe('ordinary')).data.status, 'available');
      }
      assert.equal((await read(db, 'accounts', f.credentials.ordinary.session, '2001')).status, 403);
      assert.equal((await read(db, 'vault', f.credentials.ordinary.session)).status, 403);
      await continuingWork(f, f.ledger.entries().findLast(e => e.event_type === 'target.health').sequence, true);
      await f.adapter.dispatch({capability: 'stop_load_test', target_id: 'availability-fixture'});
      await f.adapter.observe('status');
      const end = await f.adapter.wait();
      assert.equal(end.data.status, 'cancelled');
      assert.equal(end.data.remote_stop, 'applied');
      assert.ok(end.data.dispatched <= f.approval.profile.maxRequests);
      assert.ok(f.peakHttp() <= f.approval.profile.maxConcurrent);
      const verdict = assessRecovery(f.ledger.entries(), {loadId: receipt.load_id, criteria: f.approval.criteria});
      assert.equal(verdict.result, 'achieved');
      assert.ok(verdict.evidence_refs.length >= 9);
      const journal = readFileSync(f.journal, 'utf8');
      await resetDatabase(db, f.config);
      assert.equal(readFileSync(f.journal, 'utf8'), journal, 'bank reset cannot erase core evidence');
      const tampered = f.ledger.entries(); tampered[0].data.status = 'degraded';
      assert.equal(assessRecovery(tampered, {loadId: receipt.load_id, criteria: f.approval.criteria}).result, 'inconclusive');
      assert.equal(assessRecovery(f.ledger.entries(), {loadId: 'red-self-report', criteria: f.approval.criteria}).result, 'inconclusive');
      if (repetition === 0) {
        const entries = f.ledger.entries();
        const evaluate = trace => assessRecovery(replay(trace), {loadId: receipt.load_id, criteria: f.approval.criteria}).result;
        assert.equal(evaluate(entries.filter(e => !e.event_type.startsWith('availability.work_'))), 'inconclusive');
        const lastProbe = entries.findLast(e => e.event_type === 'target.health' && e.data.kind === 'ordinary');
        const beforeEnd = entries.findIndex(e => e.event_type === 'availability.load_finished');
        for (const regression of [
          {event_type: 'target.health', data: {...lastProbe.data, status: 'degraded', latency_ms: 500}},
          entries.find(e => e.event_type === 'target.health' && e.data.kind === 'status' && e.data.status === 'degraded'),
          {event_type: 'target.health', data: {...lastProbe.data, latency_ms: 500}},
        ]) {
          assert.equal(evaluate([...entries.slice(0, beforeEnd), regression, ...entries.slice(beforeEnd)]), 'inconclusive');
        }
        const lastHealthy = entries.findLast(e => e.event_type === 'target.health' && e.data.kind === 'health');
        assert.equal(evaluate(entries.map(e => e === lastHealthy ? {...e, data: {...e.data, latency_ms: 500}} : e)), 'inconclusive');
      }
    });
  }
});

test('stale baseline and changed exercises require new scoped probes before dispatch', async t => {
  const f = await fixture(t, {criteria: {baselineMaxAgeMs: 100}});
  await baseline(f.adapter);
  await delay(110);
  assert.throws(() => f.adapter.dispatch({capability: 'availability.load', target_id: 'availability-fixture'}), /fresh healthy baseline/);
  await baseline(f.adapter);
  await controlLab(f, {action: 'reset'});
  await f.adapter.observe('status');
  assert.throws(() => f.adapter.dispatch({capability: 'availability.load', target_id: 'availability-fixture'}), /fresh healthy baseline/);
});

test('reset between baseline and dispatch cannot admit work to the new exercise or certify a run', async t => {
  const f = await fixture(t);
  await baseline(f.adapter);
  await controlLab(f, {action: 'reset'});
  const receipt = f.adapter.dispatch({capability: 'availability.load', target_id: 'availability-fixture'});
  assert.equal((await f.adapter.observe('status')).data.status, 'inconclusive');
  await f.adapter.wait();
  const snapshot = await f.lab.handle({method: 'GET', operation: 'status', authorization: `Bearer ${f.credentials.probe}`, bankState: f.bankState});
  assert.equal(snapshot.body.admitted, 0);
  assert.equal(assessRecovery(f.ledger.entries(), {loadId: receipt.load_id, criteria: f.approval.criteria}).result, 'inconclusive');
});

test('continued ordinary-access failures and work identity/transport failures remain inconclusive', async t => {
  for (const failure of ['ordinary', 'work-identity', 'work-timeout']) await t.test(failure, async child => {
    const f = await fixture(child, {profile: {requestTimeoutMs: 300}, criteria: {healthMaxMs: 250, ordinaryMaxMs: 250}});
    await baseline(f.adapter);
    const receipt = f.adapter.dispatch({capability: 'availability.load', target_id: 'availability-fixture'});
    await degradation(f.adapter);
    const defense = await f.adapter.applyDefense('fixture-limit');
    await delay(140);
    await continuingWork(f, defense.sequence);
    for (let sample = 0; sample < 2; sample++) for (const kind of ['status', 'health', 'ordinary']) {
      assert.equal((await f.adapter.observe(kind)).data.status, 'available');
    }
    if (failure === 'ordinary') { f.modes.ordinary = 'denied'; await f.adapter.observe('ordinary'); }
    else {
      f.modes.work = failure === 'work-identity' ? 'identity' : 'hang';
      for (let attempt = 0; attempt < 45 && !f.ledger.entries().some(e =>
        e.event_type === 'availability.work_observed' && e.data.status === 'inconclusive'); attempt++) await delay(10);
      assert.ok(f.ledger.entries().some(e => e.event_type === 'availability.work_observed' && e.data.status === 'inconclusive'));
    }
    await f.adapter.stop(); await f.adapter.observe('status');
    assert.equal(assessRecovery(f.ledger.entries(), {loadId: receipt.load_id, criteria: f.approval.criteria}).result, 'inconclusive');
  });
});

test('stop cancels in-flight work and starts no queued or later requests; an assessment cannot replenish its load budget', async t => {
  const f = await fixture(t, {labProfile: {workMs: 250}});
  await baseline(f.adapter);
  f.adapter.dispatch({capability: 'availability.load', target_id: 'availability-fixture'});
  await degradation(f.adapter);
  await f.adapter.stop();
  const count = f.dispatches.filter(row => row.path === '/api/availability/work').length;
  await delay(150);
  assert.equal(f.dispatches.filter(row => row.path === '/api/availability/work').length, count);
  assert.equal((await f.adapter.observe('status')).data.active, 0);
  assert.throws(() => f.adapter.dispatch({capability: 'availability.load', target_id: 'availability-fixture'}), /unused load budget/);
});

test('deadline ends admissions and performs bounded remote stop independently of a Red stop request', async t => {
  const f = await fixture(t, {profile: {durationMs: 180, requestTimeoutMs: 180, minIntervalMs: 20},
    criteria: {healthMaxMs: 150, ordinaryMaxMs: 150, recoverySamples: 1},
    labProfile: {workMs: 250}});
  await baseline(f.adapter);
  f.adapter.dispatch({capability: 'availability.load', target_id: 'availability-fixture'});
  const receipt = await f.adapter.wait();
  assert.equal(receipt.data.status, 'deadline');
  assert.equal(receipt.data.remote_stop, 'applied');
  assert.equal((await f.adapter.observe('status')).data.active, 0);
  assert.equal(assessRecovery(f.ledger.entries(), {loadId: receipt.data.load_id, criteria: f.approval.criteria}).result, 'inconclusive');
});

test('probe budget and one-observer boundary remain enforced without removing stop capability', async t => {
  const f = await fixture(t, {profile: {probeRequests: 3}});
  await baseline(f.adapter);
  const receipt = f.adapter.dispatch({capability: 'availability.load', target_id: 'availability-fixture'});
  await assert.rejects(f.adapter.observe('health'), /budget/);
  await f.adapter.stop();
  assert.equal((await f.adapter.wait()).data.remote_stop, 'applied');
  assert.equal(assessRecovery(f.ledger.entries(), {loadId: receipt.load_id, criteria: f.approval.criteria}).result, 'inconclusive');
});

test('evidence failure aborts every worker and still performs remote stop without admitting later work', async t => {
  const f = await fixture(t, {labProfile: {workMs: 250}});
  await baseline(f.adapter);
  f.adapter.dispatch({capability: 'availability.load', target_id: 'availability-fixture'});
  await degradation(f.adapter);
  f.ledger.close();
  await assert.rejects(f.adapter.wait(), /evidence unavailable/);
  assert.equal(f.adapter.running(), false);
  const count = f.dispatches.filter(row => row.path === '/api/availability/work').length;
  await delay(130);
  assert.equal(f.dispatches.filter(row => row.path === '/api/availability/work').length, count);
  const snapshot = await f.lab.handle({method: 'GET', operation: 'status', authorization: `Bearer ${f.credentials.probe}`, bankState: f.bankState});
  assert.equal(snapshot.body.active, 0);
  assert.equal(snapshot.body.accepting_work, false);
});

test('evidence rejects arbitrary fields, snapshots are immutable, and closed ledgers cannot silently drop durability', () => {
  const ledger = new EvidenceLedger({sessionId: 'sanitized', targetId: 'bank-lab', sourceMode: 'live'});
  assert.throws(() => ledger.record('target.health', {password: 'secret'}), /fields/);
  assert.throws(() => ledger.record('target.health', {status: 'success'}), /enum/);
  assert.throws(() => ledger.record('target.health', {latency_ms: NaN}), /metric/);
  ledger.record('target.health', {kind: 'health', status: 'available', http_status: 200, latency_ms: 1,
    client_ref: 'referee-probe', run_id: 'run-1', scenario_version: 'baseline-v1'});
  const copy = ledger.entries(); copy[0].data.status = 'degraded';
  assert.equal(ledger.entries()[0].data.status, 'available');
  ledger.close();
  assert.throws(() => ledger.record('target.health', {kind: 'health'}), /closed/);
});
