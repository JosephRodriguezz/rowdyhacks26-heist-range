// One trusted, bounded Red -> Blue -> referee rehearsal against the fixed
// disposable bank registration. No URL, profile, or credential enters from Red.
import {strict as assert} from 'node:assert';
import {spawn} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import {existsSync, readFileSync, writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {createBankRegistry, validateApproval} from '../apps/bank-lab/integration/registry.mjs';
import {BankAvailabilityAdapter} from '../apps/bank-lab/integration/adapter.mjs';
import {EvidenceLedger, assessRecovery} from '../apps/bank-lab/integration/evidence.mjs';

const origin = 'http://127.0.0.1:3001';
const privateEnv = Object.fromEntries(readFileSync(resolve('.env.bank-disposable'), 'utf8')
  .split(/\r?\n/).filter(line => /^[A-Z_]+=/.test(line)).map(line => {
    const split = line.indexOf('='); return [line.slice(0, split), line.slice(split + 1)];
  }));
const staged = JSON.parse(readFileSync(resolve('artifacts/disposable-approval.json'), 'utf8'));
const approval = validateApproval(staged.approval);
const usedApprovalPath = resolve(`artifacts/disposable-approval-used-${approval.approvalId}`);
if (existsSync(usedApprovalPath)) throw new Error('This one-exercise approval was already used');
const exact = (actual, expected) => assert.deepEqual(actual, expected);
exact({target: staged.target_id, deployment: staged.deployment, source: staged.source_mode,
  origin: staged.origin_ref, stage: staged.status},
{target: 'bank-lab', deployment: 'disposable-desktop', source: 'live',
  origin: 'disposable-loopback-3001', stage: 'staged-no-load'});
exact(approval.profile, {maxRequests: 30, maxConcurrent: 6, durationMs: 4000,
  requestTimeoutMs: 1000, minIntervalMs: 100, probeRequests: 30, controlRequests: 4});
exact(approval.criteria, {healthMaxMs: 200, ordinaryMaxMs: 200,
  recoverySamples: 3, baselineMaxAgeMs: 3000});
exact(staged.bank_profile, {maxRequests: 30, maxConcurrent: 4, durationMs: 4500,
  workMs: 250, degradedAt: 2, mitigationTtlMs: 3000, limitRps: 1, limitBurst: 1});
if (privateEnv.BANK_SCENARIO !== 'availability-training' ||
    privateEnv.BANK_AVAILABILITY_APPROVAL_ID !== approval.approvalId ||
    privateEnv.BANK_AVAILABILITY_RUN_ID !== approval.runId ||
    privateEnv.BANK_AVAILABILITY_VERSION !== approval.scenarioVersion ||
    Object.entries({MAX_REQUESTS: 30, MAX_CONCURRENT: 4, DURATION_MS: 4500,
      WORK_MS: 250, DEGRADED_AT: 2, MITIGATION_TTL_MS: 3000,
      LIMIT_RPS: 1, LIMIT_BURST: 1}).some(([key, value]) =>
      privateEnv[`BANK_AVAILABILITY_${key}`] !== String(value))) {
  throw new Error('Disposable bank environment does not match the approved exercise');
}
const credentials = {load: privateEnv.BANK_AVAILABILITY_LOAD_TOKEN,
  probe: privateEnv.BANK_AVAILABILITY_PROBE_TOKEN,
  executor: privateEnv.BANK_AVAILABILITY_EXECUTOR_TOKEN};
if (Object.values(credentials).some(value => !/^[a-f0-9]{64}$/.test(value ?? '')) ||
    new Set(Object.values(credentials)).size !== 3 ||
    !/^[a-f0-9]{64}$/.test(privateEnv.BANK_CUSTOMER_PASSWORD ?? '')) {
  throw new Error('Disposable bank credentials are missing or invalid');
}

// Bootstrap has only four fixed ordinary requests: health, login, accounts,
// and logout. Read at most 16 KiB per response; reject redirects and timeouts.
let bootstrapRequests = 0;
async function bootstrap(path, options = {}) {
  if (++bootstrapRequests > 4) throw new Error('Bootstrap request ceiling reached');
  const response = await fetch(origin + path, {redirect: 'manual',
    signal: AbortSignal.timeout(1000), ...options});
  if (response.status >= 300 && response.status < 400) throw new Error('Bootstrap redirect rejected');
  const chunks = []; let bytes = 0;
  for await (const chunk of response.body) {
    bytes += chunk.byteLength;
    if (bytes > 16_384) throw new Error('Bootstrap response too large');
    chunks.push(chunk);
  }
  return {response, body: JSON.parse(Buffer.concat(chunks).toString('utf8'))};
}

function askBlue(context) {
  return new Promise((resolveResult, reject) => {
    const executable = process.env.HEIST_PYTHON || 'python';
    const child = spawn(executable, [resolve('scripts/observe-disposable-blue.py')],
      {cwd: process.cwd(), stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true});
    let output = '', bytes = 0, settled = false;
    const timer = setTimeout(() => child.kill(), 1500);
    child.stdout.on('data', chunk => {
      bytes += chunk.length;
      if (bytes > 65_536) child.kill();
      else output += chunk.toString('utf8');
    });
    child.on('error', error => { if (!settled) { settled = true; clearTimeout(timer); reject(error); } });
    child.on('close', code => {
      clearTimeout(timer);
      if (settled) return;
      settled = true;
      if (code !== 0 || bytes > 65_536) { reject(new Error('Blue observation failed')); return; }
      try { resolveResult(JSON.parse(output)); } catch { reject(new Error('Blue output invalid')); }
    });
    child.stdin.end(JSON.stringify(context));
  });
}

const assessmentId = `disposable-${randomUUID().replaceAll('-', '').slice(0, 20)}`;
const ledger = new EvidenceLedger({sessionId: assessmentId, targetId: 'bank-lab',
  sourceMode: 'live', directory: resolve('artifacts/disposable-evidence')});
let adapter, cookie, loadId, blueOutput, phase = 'bootstrap';
let verdict = {result: 'inconclusive', evidence_refs: []};
const reportPath = resolve(`artifacts/disposable-${assessmentId}.json`);
try {
  const health = await bootstrap('/api/health');
  if (health.response.status !== 200 || health.body.status !== 'ready' ||
      health.body.target_id !== 'bank-lab' || health.body.run_id !== approval.runId ||
      health.body.scenario_version !== approval.scenarioVersion) throw new Error('Bank identity changed');
  const login = await bootstrap('/api/login', {method: 'POST',
    headers: {'Content-Type': 'application/json', Origin: origin},
    body: JSON.stringify({username: 'customer', password: privateEnv.BANK_CUSTOMER_PASSWORD})});
  cookie = login.response.headers.get('set-cookie')?.match(/^bank_session=([a-f0-9]{64});/)?.[1];
  if (login.response.status !== 200 || !cookie) throw new Error('Synthetic login failed');
  const accounts = await bootstrap('/api/accounts', {headers: {Cookie: `bank_session=${cookie}`}});
  const rows = accounts.body.accounts;
  if (accounts.response.status !== 200 || !Array.isArray(rows) || rows.length !== 2 ||
      rows.some(row => row.owner_id !== rows[0].owner_id || !/^\d{4}$/.test(row.account_id)) ||
      new Set(rows.map(row => row.account_id)).size !== 2) throw new Error('Authorized accounts failed');
  credentials.ordinary = {session: cookie, ownerId: rows[0].owner_id,
    accountIds: rows.map(row => row.account_id)};
  phase = 'baseline';
  const registry = createBankRegistry({deployment: 'disposable-desktop', approval});
  adapter = new BankAvailabilityAdapter({registry, credentials, ledger,
    approvedDefenseIds: ['disposable-approved-load-limit']});
  for (const kind of ['status', 'health', 'ordinary']) {
    const sample = await adapter.observe(kind);
    if (sample.data.status !== 'available') throw new Error('Fresh bank baseline is inconclusive');
  }
  console.log('Healthy registered bank baseline verified.');
  writeFileSync(usedApprovalPath,
    JSON.stringify({approval_ref: approval.approvalId, assessment_id: assessmentId,
      attempted_at: new Date().toISOString()}) + '\n', {flag: 'wx'});
  phase = 'red-load';
  loadId = adapter.dispatch({capability: 'start_load_test', target_id: 'bank-lab'}).load_id;
  console.log('Bounded Red load dispatched.');
  let defenseApplied = false;
  for (let step = 0; step < 8 && adapter.running(); step++) {
    await delay(55);
    const sample = await adapter.observe('status');
    if (sample.data.status === 'inconclusive') throw new Error('Bank status became inconclusive');
    const telemetry = adapter.telemetry();
    const context = {assessment_id: assessmentId, target_id: 'bank-lab',
      target_version: approval.scenarioVersion, data_source: 'live', window: telemetry.window};
    phase = 'blue-observation';
    blueOutput = await askBlue(context);
    const proposal = blueOutput.defense_proposals?.[0];
    if (!proposal) continue;
    if (sample.data.status !== 'degraded' || blueOutput.assessment !== 'suspected_http_flood' ||
        blueOutput.defense_proposals.length !== 1 || proposal.target_id !== 'bank-lab' ||
        proposal.data_source !== 'live' || proposal.assessment_id !== assessmentId ||
        proposal.window_id !== telemetry.window.window_id ||
        proposal.action_type !== 'limit_http_source' ||
        proposal.parameters?.source_ref !== 'load-demo' ||
        proposal.parameters?.rate_per_second !== 1 || proposal.parameters?.burst !== 1 ||
        proposal.parameters?.ttl_seconds !== 3 ||
        telemetry.policy.rate !== 1 || telemetry.policy.burst !== 1 || telemetry.policy.ttlMs !== 3000) {
      throw new Error('Blue proposal does not match current approved target telemetry');
    }
    phase = 'defense';
    const applied = await adapter.applyDefense('disposable-approved-load-limit');
    if (applied.data.status !== 'applied') throw new Error('Blue defense not applied');
    defenseApplied = true;
    console.log('Blue source limit applied; recovery remains unverified.');
    break;
  }
  if (!defenseApplied) throw new Error('No evidence-backed Blue limit was proposed');
  phase = 'recovery-probes';
  for (let step = 0; step < 8; step++) {
    await delay(50);
    const sample = await adapter.observe('status');
    if (sample.data.status === 'available') break;
  }
  for (let sample = 0; sample < approval.criteria.recoverySamples; sample++) {
    await delay(120);
    for (const kind of ['status', 'health', 'ordinary']) await adapter.observe(kind);
  }
  await delay(150);
  await adapter.dispatch({capability: 'stop_load_test', target_id: 'bank-lab'});
  await adapter.wait();
  await adapter.observe('status');
  phase = 'referee';
  verdict = assessRecovery(ledger.entries(), {loadId, criteria: approval.criteria,
    requirePolicyRefusals: true, requiredPolicy: {rate: 1, burst: 1, ttlMs: 3000, suspectRps: 4}});
  const events = ledger.entries();
  const report = {assessment_id: assessmentId, target_id: 'bank-lab', source_mode: 'live',
    origin_ref: 'disposable-loopback-3001', run_id: approval.runId,
    approval_ref: approval.approvalId, criteria: approval.criteria,
    blue_assessment: blueOutput.assessment,
    load_requests: events.filter(e => e.event_type === 'availability.work_started').length,
    rate_refusals: events.filter(e => e.data.refusal_reason === 'rate_limit').length,
    verdict, evidence_file: `artifacts/disposable-evidence/${assessmentId}.jsonl`};
  writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
  console.log(JSON.stringify(report));
  if (verdict.result !== 'achieved') process.exitCode = 1;
} catch {
  const events = ledger.entries();
  const report = {assessment_id: assessmentId, target_id: 'bank-lab', source_mode: 'live',
    origin_ref: 'disposable-loopback-3001', run_id: approval.runId,
    approval_ref: approval.approvalId, criteria: approval.criteria, failed_at: phase, verdict,
    load_requests: events.filter(e => e.event_type === 'availability.work_started').length,
    evidence_file: `artifacts/disposable-evidence/${assessmentId}.jsonl`};
  writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
  console.error(`Disposable availability rehearsal is inconclusive at ${phase}; private evidence was retained.`);
  process.exitCode = 1;
} finally {
  if (adapter?.running()) await adapter.stop().catch(() => {});
  if (cookie && bootstrapRequests < 4) {
    await bootstrap('/api/logout', {method: 'POST',
      headers: {Origin: origin, Cookie: `bank_session=${cookie}`}}).catch(() => {});
  }
  ledger.close();
}
