// Exactly six ordinary requests to the separately published disposable bank.
// This measures a healthy baseline; it never opens an availability exercise.
import {readFileSync, mkdirSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {dirname, resolve} from 'node:path';

const origin = 'http://127.0.0.1:3001';
const environment = resolve('.env.bank-disposable');
const destination = resolve('artifacts/disposable-baseline.json');
const values = Object.fromEntries(readFileSync(environment, 'utf8').split(/\r?\n/)
  .filter(line => /^[A-Z_]+=/.test(line)).map(line => {
    const split = line.indexOf('=');
    return [line.slice(0, split), line.slice(split + 1)];
  }));
if (values.BANK_SCENARIO !== 'baseline' || !/^[a-f0-9]{64}$/.test(values.BANK_CUSTOMER_PASSWORD ?? '')) {
  throw new Error('A private baseline disposable-bank environment is required');
}
let sent = 0;
const samples = [];
async function request(kind, path, options = {}) {
  if (++sent > 6) throw new Error('Baseline request budget exhausted');
  const started = performance.now();
  const response = await fetch(origin + path, {redirect: 'manual', signal: AbortSignal.timeout(3000),
    ...options});
  if (response.status >= 300 && response.status < 400) throw new Error('Redirect rejected');
  const latencyMs = Math.round((performance.now() - started) * 100) / 100;
  samples.push({kind, status: response.status, latency_ms: latencyMs});
  return {response, body: await response.json()};
}
let cookie;
try {
  const first = await request('health', '/api/health');
  if (first.response.status !== 200 || first.body.status !== 'ready' || first.body.target_id !== 'bank-lab' ||
      !/^[a-f0-9-]{36}$/.test(first.body.run_id ?? '') || first.body.scenario_version !== 'baseline-v1') {
    throw new Error('Disposable bank identity or readiness failed');
  }
  const {run_id: runId, scenario_version: scenarioVersion} = first.body;
  const login = await request('login', '/api/login', {method: 'POST',
    headers: {'Content-Type': 'application/json', Origin: origin},
    body: JSON.stringify({username: 'customer', password: values.BANK_CUSTOMER_PASSWORD})});
  cookie = login.response.headers.get('set-cookie')?.match(/^bank_session=([a-f0-9]{64});/)?.[1];
  if (login.response.status !== 200 || !cookie) throw new Error('Synthetic customer login failed');
  const accountIds = [];
  for (let index = 0; index < 2; index++) {
    const accounts = await request('ordinary', '/api/accounts', {headers: {Cookie: `bank_session=${cookie}`}});
    if (accounts.response.status !== 200 || !Array.isArray(accounts.body.accounts) ||
        accounts.body.accounts.length !== 2) throw new Error('Authorized account access failed');
    const ids = accounts.body.accounts.map(account => account.account_id);
    if (new Set(ids).size !== 2 || (index && ids.join() !== accountIds.join())) {
      throw new Error('Authorized accounts changed during baseline');
    }
    if (!index) accountIds.push(...ids);
  }
  const second = await request('health', '/api/health');
  if (second.response.status !== 200 || second.body.run_id !== runId ||
      second.body.scenario_version !== scenarioVersion) throw new Error('Bank run changed during baseline');
  const logout = await request('logout', '/api/logout', {method: 'POST',
    headers: {Origin: origin, Cookie: `bank_session=${cookie}`}});
  if (logout.response.status !== 200) throw new Error('Synthetic customer logout failed');
  cookie = undefined;
  const report = {target_id: 'bank-lab', source_mode: 'isolated-live-bank',
    origin_ref: 'disposable-loopback-3001', run_id: runId, scenario_version: scenarioVersion,
    sampled_at: new Date().toISOString(), samples};
  report.evidence_ref = `baseline-${createHash('sha256').update(JSON.stringify(report)).digest('hex').slice(0, 16)}`;
  mkdirSync(dirname(destination), {recursive: true});
  writeFileSync(destination, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
  console.log(JSON.stringify(report));
} catch {
  // No response bodies, passwords, cookies, or source URLs in failure output.
  console.error('Disposable bank baseline failed; no availability traffic was sent.');
  process.exitCode = 1;
}
