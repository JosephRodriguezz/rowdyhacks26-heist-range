import {test} from 'node:test';
import assert from 'node:assert/strict';
import {AvailabilityLab, createAvailabilityLabFromEnv} from '../src/lib/availability-lab.mjs';

const approval = {approvalId: 'unit-test-approval', runId: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
  scenarioVersion: 'bank-baseline-v1'};
const bankState = {run_id: approval.runId, scenario_version: approval.scenarioVersion};
const credentials = {load: 'a'.repeat(64), probe: 'b'.repeat(64), executor: 'c'.repeat(64)};
const profile = {maxRequests: 6, maxConcurrent: 3, durationMs: 1000, workMs: 40,
  degradedAt: 2, mitigationTtlMs: 60};
const makeLab = changes => new AvailabilityLab({enabled: true, approval, credentials,
  profile: {...profile, ...changes}});
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const exercisePins = new WeakMap();
const invoke = (lab, operation, input = {}, changes = {}) => lab.handle({
  method: operation === 'status' ? 'GET' : 'POST', operation,
  authorization: `Bearer ${credentials[{work: 'load', status: 'probe', control: 'executor'}[operation]]}`,
  bankState, input, expectedExerciseId: exercisePins.get(lab), ...changes,
}).then(result => {
  if (typeof result.body.exercise_id === 'string') exercisePins.set(lab, result.body.exercise_id);
  return result;
});
const status = lab => invoke(lab, 'status');
const control = (lab, action, extra = {}) => invoke(lab, 'control', {action, ...extra});
async function initializeLab(changes) {
  const lab = makeLab(changes);
  await status(lab);
  return lab;
}
const env = () => ({BANK_SCENARIO: 'availability-training',
  BANK_AVAILABILITY_APPROVAL_ID: approval.approvalId, BANK_AVAILABILITY_RUN_ID: approval.runId,
  BANK_AVAILABILITY_VERSION: approval.scenarioVersion,
  BANK_AVAILABILITY_MAX_REQUESTS: '6', BANK_AVAILABILITY_MAX_CONCURRENT: '3',
  BANK_AVAILABILITY_DURATION_MS: '1000', BANK_AVAILABILITY_WORK_MS: '40',
  BANK_AVAILABILITY_DEGRADED_AT: '2', BANK_AVAILABILITY_MITIGATION_TTL_MS: '60',
  BANK_AVAILABILITY_LOAD_TOKEN: credentials.load, BANK_AVAILABILITY_PROBE_TOKEN: credentials.probe,
  BANK_AVAILABILITY_EXECUTOR_TOKEN: credentials.executor});

test('factory is disabled unless every approval, profile, and credential field is explicit and valid', async () => {
  assert.equal((await status(new AvailabilityLab())).status, 404);
  assert.equal((await status(createAvailabilityLabFromEnv({}))).status, 404);
  assert.equal((await status(createAvailabilityLabFromEnv({...env(), BANK_SCENARIO: 'baseline'}))).status, 404);
  for (const key of Object.keys(env())) {
    const incomplete = env();
    delete incomplete[key];
    assert.equal((await status(createAvailabilityLabFromEnv(incomplete))).status, 404, key);
  }
  assert.equal((await status(createAvailabilityLabFromEnv(env()))).status, 200);
  for (const value of ['NaN', 'Infinity', '1e3', '1.5', '-1', '0', ' 3', '3 ', '03', true, 3]) {
    assert.equal((await status(createAvailabilityLabFromEnv({...env(),
      BANK_AVAILABILITY_MAX_CONCURRENT: value}))).status, 404);
  }
});

test('constructor rejects coercion, nonfinite numbers, excessive bounds, and inconsistent profiles', () => {
  for (const field of Object.keys(profile)) {
    for (const value of ['1', true, null, NaN, Infinity, -Infinity, 0, -1, 1.5, {}]) {
      assert.throws(() => makeLab({[field]: value}), /profile is invalid/, `${field}: ${String(value)}`);
    }
  }
  for (const changes of [{maxRequests: 61}, {maxConcurrent: 13}, {durationMs: 10001},
    {workMs: 251}, {degradedAt: 13}, {mitigationTtlMs: 10001},
    {maxRequests: 2, maxConcurrent: 3}, {degradedAt: 4}, {durationMs: 10, workMs: 20}]) {
    assert.throws(() => makeLab(changes), /profile is invalid/);
  }
  assert.throws(() => new AvailabilityLab({enabled: 'true'}), /enablement is invalid/);
  assert.throws(() => new AvailabilityLab({enabled: true, profile, credentials,
    approval: {...approval, runId: 'not-a-bank-run'}}), /approval configuration is invalid/);
  assert.throws(() => new AvailabilityLab({enabled: true, profile, credentials,
    approval: {...approval, approvalId: '<script>bad</script>'}}), /approval configuration is invalid/);
});

test('private authentication separates load, probe, and executor capabilities', async () => {
  const lab = await initializeLab();
  for (const authorization of [undefined, '', credentials.load, 'Basic token',
    `Bearer ${'d'.repeat(64)}`, `Bearer ${credentials.load.toUpperCase()}`, `Bearer ${credentials.load}extra`]) {
    assert.equal((await invoke(lab, 'work', {}, {authorization})).status, 401);
  }
  for (const operation of ['status', 'work', 'control']) {
    const own = {status: 'probe', work: 'load', control: 'executor'}[operation];
    for (const other of Object.keys(credentials).filter(key => key !== own)) {
      assert.equal((await invoke(lab, operation, {}, {authorization: `Bearer ${credentials[other]}`})).status, 403);
    }
  }
  assert.equal((await invoke(lab, 'status', {}, {method: 'POST'})).status, 405);
  assert.equal((await invoke(lab, 'work', {}, {method: 'GET'})).status, 405);
  assert.equal((await invoke(lab, 'status', {}, {operation: 'unknown'})).status, 404);
  assert.throws(() => new AvailabilityLab({enabled: true, approval, profile,
    credentials: {...credentials, executor: credentials.load}}), /credential configuration is invalid/);
  assert.throws(() => new AvailabilityLab({enabled: true, approval, profile,
    credentials: {...credentials, load: 'x'.repeat(64)}}), /credential configuration is invalid/);
});

test('trusted bank run and version pins fail closed and cancel pending work after a bank reset', async () => {
  const lab = await initializeLab({workMs: 200});
  const pending = invoke(lab, 'work');
  assert.equal((await status(lab)).body.active, 1);
  for (const bad of [undefined, {}, {...bankState, run_id: 'new-run'},
    {...bankState, scenario_version: 'new-version'}]) {
    const response = await invoke(lab, 'status', {}, {bankState: bad});
    assert.equal(response.status, 409);
    assert.deepEqual(response.body, {error: 'Availability approval does not match bank state'});
  }
  assert.equal((await pending).status, 409);
  assert.equal((await status(lab)).body.active, 0);
  assert.equal((await invoke(lab, 'work')).status, 429);
});

test('preflight rejects requests without reading bank state or mutating ongoing work', async () => {
  const lab = await initializeLab({workMs: 100});
  const pending = invoke(lab, 'work');
  assert.equal(lab.authorize({method: 'GET', operation: 'status',
    authorization: `Bearer ${credentials.probe}`}), null);
  assert.equal(lab.authorize({method: 'POST', operation: 'work',
    authorization: `Bearer ${credentials.load}`}), null);
  assert.equal(lab.authorize({method: 'POST', operation: 'control',
    authorization: `Bearer ${credentials.executor}`}), null);
  assert.equal(new AvailabilityLab().authorize({}).status, 404);
  for (const request of [{method: 'POST', operation: 'control'},
    {method: 'POST', operation: 'control', authorization: `Bearer ${credentials.load}`},
    {method: 'POST', operation: 'status', authorization: `Bearer ${credentials.probe}`}]) {
    const denial = lab.authorize(request);
    assert.ok([401, 403, 405].includes(denial.status));
    assert.deepEqual(await lab.handle({...request, bankState: undefined}), denial);
  }
  const observed = await status(lab);
  assert.equal(observed.body.active, 1);
  assert.equal(observed.body.admitted, 1);
  assert.equal(observed.body.accepting_work, true);
  assert.equal((await pending).status, 200);
});

test('mutating operations require the current exercise pin and stale controls cannot affect a reset exercise', async () => {
  const lab = await initializeLab({workMs: 100});
  const original = (await status(lab)).body.exercise_id;
  for (const expectedExerciseId of [undefined, '', 'other-exercise', 123]) {
    assert.equal((await invoke(lab, 'work', {}, {expectedExerciseId})).status, 409);
    assert.equal((await invoke(lab, 'control', {action: 'reset'}, {expectedExerciseId})).status, 409);
  }
  assert.equal((await status(lab)).body.admitted, 0);
  const reset = await control(lab, 'reset');
  const current = reset.body.exercise_id;
  assert.notEqual(current, original);
  const pending = invoke(lab, 'work');
  for (const input of [{action: 'stop'}, {action: 'reset'},
    {action: 'limit_load', client_ref: 'load-demo'}, {action: 'restore', client_ref: 'load-demo'}]) {
    assert.equal((await invoke(lab, 'control', input, {expectedExerciseId: original})).status, 409);
  }
  assert.equal((await invoke(lab, 'work', {}, {expectedExerciseId: original})).status, 409);
  const observed = await invoke(lab, 'status', {}, {expectedExerciseId: undefined});
  assert.equal(observed.status, 200);
  assert.equal(observed.body.exercise_id, current);
  assert.equal(observed.body.active, 1);
  assert.equal(observed.body.admitted, 1);
  assert.equal(observed.body.rate_limited, false);
  assert.equal((await pending).status, 200);
  assert.equal((await control(lab, 'stop')).status, 200);
});

test('admission has a fixed active ceiling and no hidden queue, with measured degradation and automatic recovery', async () => {
  const lab = await initializeLab({workMs: 100});
  const first = invoke(lab, 'work');
  assert.equal((await status(lab)).body.status, 'available');
  const second = invoke(lab, 'work');
  const third = invoke(lab, 'work');
  const degraded = await status(lab);
  assert.equal(degraded.body.status, 'degraded');
  assert.equal(degraded.body.active, 3);
  assert.equal(degraded.body.max_active, 3);
  assert.equal(degraded.body.degraded_at, 2);
  const rejected = await invoke(lab, 'work');
  assert.equal(rejected.status, 429);
  assert.equal(rejected.body.admitted, 3);
  assert.equal((await Promise.all([first, second, third])).every(result => result.status === 200), true);
  const recovered = await status(lab);
  assert.equal(recovered.body.status, 'available');
  assert.equal(recovered.body.active, 0);
  assert.equal(recovered.body.admitted, 3);
  assert.equal(recovered.body.completed, 3);
  assert.equal(recovered.body.remaining_requests, 3);
  assert.deepEqual(recovered.body.transitions.map(row => row.status), ['available', 'degraded', 'available']);
  assert.ok(recovered.body.transitions.every(row => row.status ===
    (row.active >= recovered.body.degraded_at ? 'degraded' : 'available')));
});

test('global exercise quota cannot replenish with elapsed time or concurrency rejection', async () => {
  const lab = await initializeLab({maxRequests: 3, maxConcurrent: 1, degradedAt: 1, workMs: 10});
  for (let count = 0; count < 3; count++) assert.equal((await invoke(lab, 'work')).status, 200);
  for (let count = 0; count < 3; count++) assert.equal((await invoke(lab, 'work')).status, 429);
  await sleep(30);
  const observed = await status(lab);
  assert.equal(observed.body.admitted, 3);
  assert.equal(observed.body.remaining_requests, 0);
  assert.equal(observed.body.accepting_work, false);
});

test('exercise deadline stops admission and aborts unfinished work, including work started near deadline', async () => {
  const lab = await initializeLab({durationMs: 180, workMs: 100});
  assert.equal((await invoke(lab, 'work')).status, 200);
  const pending = invoke(lab, 'work');
  const cancelled = await pending;
  assert.equal(cancelled.status, 409);
  const observed = await status(lab);
  assert.equal(observed.body.active, 0);
  assert.equal(observed.body.admitted, 2);
  assert.equal(observed.body.completed, 1);
  assert.equal(observed.body.accepting_work, false);
  assert.equal((await invoke(lab, 'work')).status, 429);
});

test('executor stop promptly drains pending work and forbids all late admissions until explicit reset', async () => {
  const lab = await initializeLab({workMs: 250});
  const pending = [invoke(lab, 'work'), invoke(lab, 'work'), invoke(lab, 'work')];
  const stopped = await control(lab, 'stop');
  assert.equal(stopped.status, 200);
  assert.equal(stopped.body.applied, true);
  assert.equal(stopped.body.run_id, bankState.run_id);
  assert.equal(stopped.body.scenario_version, bankState.scenario_version);
  assert.equal(stopped.body.active, 0);
  assert.equal(stopped.body.status, 'available');
  assert.equal(stopped.body.accepting_work, false);
  const results = await Promise.race([Promise.all(pending), sleep(100).then(() => 'not-drained')]);
  assert.notEqual(results, 'not-drained');
  assert.ok(results.every(result => result.status === 409));
  assert.equal(stopped.body.completed, 0);
  assert.equal((await invoke(lab, 'work')).status, 429);
  await sleep(260);
  assert.equal((await status(lab)).body.completed, 0);
});

test('reset is executor-only, requires idle state, rotates exercise identity, and preserves sequence history', async () => {
  const lab = await initializeLab({maxRequests: 1, maxConcurrent: 1, degradedAt: 1});
  const original = (await status(lab)).body;
  const pending = invoke(lab, 'work');
  assert.equal((await control(lab, 'reset')).status, 409);
  await pending;
  const reset = await control(lab, 'reset');
  assert.equal(reset.status, 200);
  assert.notEqual(reset.body.exercise_id, original.exercise_id);
  assert.equal(reset.body.admitted, 0);
  assert.equal(reset.body.remaining_requests, 1);
  assert.equal(reset.body.accepting_work, true);
  assert.equal(reset.body.transitions[0].exercise_id, original.exercise_id);
  assert.equal(reset.body.transitions.at(-1).exercise_id, reset.body.exercise_id);
  assert.ok(reset.body.transitions.every((row, index, rows) => index === 0 || row.sequence > rows[index - 1].sequence));
  assert.equal((await invoke(lab, 'work')).status, 200);
});

test('narrow mitigation blocks only new load work, preserves referee probes, expires, and can be restored', async () => {
  const lab = await initializeLab({workMs: 100, mitigationTtlMs: 160});
  const pending = invoke(lab, 'work');
  const limit = await control(lab, 'limit_load', {client_ref: 'load-demo'});
  assert.equal(limit.status, 200);
  assert.equal(limit.body.applied, true);
  assert.equal(limit.body.rate_limited, true);
  assert.equal((await invoke(lab, 'work')).status, 429);
  assert.equal((await status(lab)).status, 200);
  assert.equal((await pending).status, 200);
  await sleep(90);
  assert.equal((await status(lab)).body.rate_limited, false);
  assert.equal((await invoke(lab, 'work')).status, 200);
  await control(lab, 'limit_load', {client_ref: 'load-demo'});
  assert.equal((await control(lab, 'restore', {client_ref: 'load-demo'})).body.rate_limited, false);
  assert.equal((await invoke(lab, 'work')).status, 200);
  for (const client_ref of ['referee-probe', 'core-executor', 'all', 'customer', '127.0.0.1']) {
    assert.equal((await control(lab, 'limit_load', {client_ref})).status, 400);
  }
});

test('callers cannot pick work cost, set health, spoof client refs, or change limits/control TTL', async () => {
  const lab = await initializeLab();
  for (const input of [{workMs: 1}, {client_ref: 'referee-probe'}, {status: 'degraded'},
    {url: 'https://example.invalid'}, [], null, 'input', Object.create({client_ref: 'load-demo'})]) {
    assert.equal((await invoke(lab, 'work', input)).status, 400);
    assert.equal((await invoke(lab, 'status', input)).status, 400);
  }
  for (const input of [{action: 'limit_load', client_ref: 'load-demo', ttl_ms: 100000},
    {action: 'limit_load'}, {action: 'reset', maxRequests: 60},
    {action: 'restore'}, {action: 'stop', client_ref: 'all'}, {action: 'set_degraded'}]) {
    assert.equal((await invoke(lab, 'control', input)).status, 400);
  }
  const accessor = Object.defineProperty({}, 'term', {get() {throw new Error(credentials.load);}});
  assert.equal((await invoke(lab, 'work', accessor)).status, 400);
  assert.equal((await status(lab)).body.admitted, 0);
});

test('operator objects cannot mutate an approved profile, credentials, or pinned run after construction', async () => {
  const mutableProfile = {...profile, maxRequests: 1, maxConcurrent: 1, degradedAt: 1};
  const mutableApproval = {...approval};
  const mutableCredentials = {...credentials};
  const lab = new AvailabilityLab({enabled: true, profile: mutableProfile,
    approval: mutableApproval, credentials: mutableCredentials});
  await status(lab);
  mutableProfile.maxRequests = 60;
  mutableProfile.workMs = 100000;
  mutableApproval.runId = 'changed';
  mutableCredentials.load = 'd'.repeat(64);
  assert.equal((await invoke(lab, 'work')).status, 200);
  assert.equal((await invoke(lab, 'work')).status, 429);
  assert.equal((await status(lab)).body.run_id, approval.runId);
});

test('bounded evidence is copied, ordered, sanitized and attached to the correct exercise', async () => {
  const lab = await initializeLab();
  for (let index = 0; index < 140; index++) await control(lab, 'reset');
  const response = await status(lab);
  assert.equal(response.body.transitions.length, 64);
  assert.ok(Buffer.byteLength(JSON.stringify(response.body)) < 16_384);
  assert.ok(response.body.transitions[0].sequence > 1);
  assert.deepEqual(Object.keys(response.body.transitions[0]).sort(),
    ['sequence', 'timestamp', 'exercise_id', 'status', 'active'].sort());
  assert.equal(response.body.target_id, 'bank-lab');
  assert.equal(response.body.source, 'availability-training');
  const rendered = JSON.stringify({response, lab});
  for (const secret of Object.values(credentials)) assert.equal(rendered.includes(secret), false);
  for (const field of ['authorization', 'cookie', 'password', 'headers', 'source_address', 'approvalId']) {
    assert.equal(rendered.includes(field), false);
  }
  response.body.transitions[0].status = 'compromised';
  response.body.transitions.push({sequence: -1});
  const reread = await status(lab);
  assert.equal(reread.body.transitions.length, 64);
  assert.equal(reread.body.transitions.some(row => row.status === 'compromised'), false);
  const malicious = await invoke(lab, 'work', {secret: credentials.load});
  assert.equal(JSON.stringify(malicious).includes(credentials.load), false);
});
