// Private bounded stdin/stdout adapter, no HTTP control listener. Core owns the
// subprocess and its opaque assessment ID. Every target is created here.
import {createInterface} from 'node:readline';
import {createCoreFixture} from './core-fixture.mjs';
import {assessRecovery} from './evidence.mjs';

const args = process.argv.slice(2);
if (args.length < 1 || args.length > 2 || !/^[A-Za-z0-9_-]{1,80}$/.test(args[0])) process.exit(2);
let fixture, cursor = 0, commands = 0, loadId, closing = false;
const send = value => process.stdout.write(JSON.stringify(value) + '\n');
async function close() {
  if (closing) return; closing = true;
  try { await fixture?.close(); } finally { process.exit(0); }
}
// Independent last resort: parent disappearance or stalled control cannot keep
// a disposable target alive indefinitely. Load has its separate 4s deadline.
const watchdog = setTimeout(close, 20_000); watchdog.unref();
process.on('SIGTERM', close); process.on('SIGINT', close);
try {
  fixture = await createCoreFixture(args[0], args[1]);
  send({ready: true, target_id: 'availability-fixture', target_version: fixture.approval.scenarioVersion,
    data_source: 'fixture', approval: fixture.approval});
  const lines = createInterface({input: process.stdin, crlfDelay: Infinity});
  for await (const line of lines) {
    if (++commands > 80 || Buffer.byteLength(line) > 16_384) break;
    let request;
    try {
      request = JSON.parse(line);
      if (!request || Object.keys(request).some(k => !['id', 'op', 'kind', 'proposal', 'window_id'].includes(k)) ||
          !Number.isSafeInteger(request.id)) throw new Error();
      const {adapter, ledger} = fixture;
      let result = null;
      if (request.op === 'observe') result = await adapter.observe(request.kind);
      else if (request.op === 'dispatch') {
        result = await adapter.dispatch(request.proposal); if (result?.load_id) loadId = result.load_id;
      } else if (request.op === 'apply') {
        if (adapter.telemetry().window.window_id !== request.window_id) throw new Error();
        result = await adapter.applyDefense('core-approved-load-limit');
      } else if (request.op === 'pause') { await adapter.pause(); result = {paused: true}; }
      else if (request.op === 'resume') { adapter.resume(); result = {paused: false}; }
      else if (request.op === 'stop') result = await adapter.stop();
      else if (request.op === 'poll') result = {running: adapter.running()};
      else if (request.op === 'referee') result = assessRecovery(ledger.entries(), {
        loadId, criteria: fixture.approval.criteria, requirePolicyRefusals: true,
        requiredPolicy: {rate: 1, burst: 1, ttlMs: 3000, suspectRps: 4}});
      else if (request.op === 'close') { send({id: request.id, ok: true}); break; }
      else throw new Error();
      const entries = ledger.entries().slice(cursor); cursor += entries.length;
      let telemetry = null;
      if (request.op === 'observe' && request.kind === 'status') telemetry = adapter.telemetry();
      send({id: request.id, ok: true, result, entries, telemetry, running: adapter.running()});
    } catch { send({id: request?.id ?? -1, ok: false, code: 'bridge_operation_failed'}); }
  }
} catch { send({ready: false, code: 'fixture_start_failed'}); }
await close();
