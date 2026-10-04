// Offline referee replay. It reads retained evidence and sends no bank traffic.
import {strict as assert} from 'node:assert';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {assessRecovery} from '../apps/bank-lab/integration/evidence.mjs';

const assessmentId = process.argv[2];
if (!/^disposable-[a-f0-9]{20}$/.test(assessmentId ?? '')) {
  throw new Error('Provide a disposable assessment ID');
}
const report = JSON.parse(readFileSync(resolve(`artifacts/disposable-${assessmentId}.json`), 'utf8'));
const entries = readFileSync(resolve(`artifacts/disposable-evidence/${assessmentId}.jsonl`), 'utf8')
  .trim().split('\n').map(line => JSON.parse(line));
assert.equal(report.assessment_id, assessmentId);
assert.equal(report.target_id, 'bank-lab');
assert.equal(report.source_mode, 'live');
assert.deepEqual(report.criteria, {healthMaxMs: 200, ordinaryMaxMs: 200,
  recoverySamples: 3, baselineMaxAgeMs: 3000});
const starts = entries.filter(entry => entry.event_type === 'availability.load_started');
assert.equal(starts.length, 1);
assert.equal(report.run_id, starts[0].data.run_id);
assert.equal(report.approval_ref, starts[0].data.approval_ref);
const result = assessRecovery(entries, {loadId: starts[0].data.load_id,
  criteria: report.criteria, requirePolicyRefusals: true,
  requiredPolicy: {rate: 1, burst: 1, ttlMs: 3000, suspectRps: 4}});
assert.deepEqual(result, report.verdict);
console.log(JSON.stringify({assessment_id: assessmentId, target_id: 'bank-lab',
  source_mode: 'live', ledger_entries: entries.length, result: result.result,
  evidence_refs: result.evidence_refs.length}));
