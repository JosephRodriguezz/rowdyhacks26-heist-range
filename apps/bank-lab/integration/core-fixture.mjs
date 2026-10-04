// Owned disposable target used by core correctness checks. No destination or
// private bank environment can be supplied. This does not start Next.js/Docker.
import {createServer} from 'node:http';
import {randomBytes} from 'node:crypto';
import {PGlite} from '@electric-sql/pglite';
import {AvailabilityLab} from '../src/lib/availability-lab.mjs';
import {login, read, resetDatabase, state} from '../src/lib/bank.mjs';
import {createDisposableRegistry} from './registry.mjs';
import {BankAvailabilityAdapter} from './adapter.mjs';
import {EvidenceLedger} from './evidence.mjs';

export async function createCoreFixture(assessmentId, fixtureCase = 'normal') {
  if (!['normal', 'ordinary_denied', 'capacity_only', 'expired'].includes(fixtureCase)) throw new Error('Unknown fixture');
  const engine = new PGlite(); await engine.waitReady;
  const db = {query: async (sql, values) => values ? engine.query(sql, values) : (await engine.exec(sql)).at(-1)};
  let server, adapter, ledger;
  const close = async () => {
    try { if (adapter?.running()) await adapter.stop(); } finally {
      if (server?.listening) { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
      ledger?.close(); await engine.close();
    }
  };
  try {
    const config = {customerPassword: randomBytes(24).toString('hex'), vaultPassword: randomBytes(24).toString('hex')};
    await resetDatabase(db, config);
    const bankState = await state(db);
    const customer = await login(db, 'customer', config.customerPassword);
    const own = await read(db, 'accounts', customer.token);
    const credentials = {load: randomBytes(32).toString('hex'), probe: randomBytes(32).toString('hex'),
      executor: randomBytes(32).toString('hex'), ordinary: {session: customer.token,
        ownerId: own.body.accounts[0].owner_id, accountIds: own.body.accounts.map(a => a.account_id)}};
    const approval = {approvalId: 'core-disposable-profile', scope: 'isolated-lab', runId: bankState.run_id,
      scenarioVersion: bankState.scenario_version, baselineEvidenceRefs: ['core-fixture-baseline'],
      profile: {maxRequests: 60, maxConcurrent: 6, durationMs: 4000, requestTimeoutMs: 500,
        minIntervalMs: 100, probeRequests: 30, controlRequests: 4},
      criteria: {healthMaxMs: 400, ordinaryMaxMs: 400, recoverySamples: 3, baselineMaxAgeMs: 1000}};
    const lab = new AvailabilityLab({enabled: true, approval, credentials,
      profile: {maxRequests: 60, maxConcurrent: 4, durationMs: 4500, workMs: 250,
        degradedAt: 2, mitigationTtlMs: 3000},
      mitigation: {ratePerSecond: 1, burst: 1}});
    let origin, applied = false;
    server = createServer(async (request, response) => {
      const reply = (status, body) => { response.writeHead(status, {'Content-Type': 'application/json'}); response.end(JSON.stringify(body)); };
      try {
        if (request.url === '/api/health') { reply(200, {status: 'ready', target_id: 'bank-lab', ...await state(db)}); return; }
        if (request.url === '/api/accounts') {
          if (applied && fixtureCase === 'ordinary_denied') { reply(403, {error: 'Fixture denial'}); return; }
          const token = request.headers.cookie?.match(/^bank_session=([a-f0-9]{64})$/)?.[1];
          const result = await read(db, 'accounts', token); reply(result.status, result.body); return;
        }
        const operation = request.url?.match(/^\/api\/availability\/(status|work|control)$/)?.[1];
        if (!operation) { reply(404, {}); return; }
        const authorization = request.headers.authorization;
        const denied = lab.authorize({method: request.method, operation, authorization});
        if (denied) { reply(denied.status, denied.body); return; }
        let input = {};
        if (request.method === 'POST') {
          if (request.headers.origin !== origin) { reply(403, {}); return; }
          let text = '';
          for await (const chunk of request) { text += chunk.toString(); if (text.length > 4096) { reply(413, {}); return; } }
          input = JSON.parse(text);
        }
        const result = await lab.handle({method: request.method, operation, authorization, input,
          bankState: await state(db), expectedExerciseId: request.headers['x-bank-exercise']});
        if (operation === 'control' && input.action === 'limit_load') {
          applied = result.status === 200;
          if (fixtureCase === 'capacity_only') await lab.handle({method: 'POST', operation, authorization,
            input: {action: 'restore', client_ref: 'load-demo'}, bankState, expectedExerciseId: result.body.exercise_id});
          if (fixtureCase === 'expired') setTimeout(() => lab.handle({method: 'POST', operation, authorization,
            input: {action: 'restore', client_ref: 'load-demo'}, bankState, expectedExerciseId: result.body.exercise_id}), 150).unref();
        }
        reply(result.status, result.body);
      } catch { if (!response.headersSent) reply(503, {}); }
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    // Never accidentally use the existing bank's reserved listener.
    if (server.address().port === 3000) throw new Error('Reserved port');
    origin = `http://127.0.0.1:${server.address().port}`;
    const registry = createDisposableRegistry(server, approval);
    ledger = new EvidenceLedger({sessionId: assessmentId, targetId: 'availability-fixture', sourceMode: 'fixture'});
    adapter = new BankAvailabilityAdapter({registry, credentials, ledger, approvedDefenseIds: ['core-approved-load-limit']});
    return {adapter, ledger, approval, close};
  } catch (error) { await close(); throw error; }
}
