// Stage an explicit, local-only profile from a measured baseline. This script
// does not enable load, recreate a container, or send availability traffic.
import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {validateApproval} from '../apps/bank-lab/integration/registry.mjs';

const reportPath = resolve('artifacts/disposable-baseline.json');
const approvalPath = resolve('artifacts/disposable-approval.json');
const envPath = resolve('.env.bank-disposable');
const baseline = JSON.parse(readFileSync(reportPath, 'utf8'));
const {evidence_ref: evidenceRef, ...payload} = baseline;
const digest = createHash('sha256').update(JSON.stringify(payload)).digest('hex').slice(0, 16);
if (evidenceRef !== `baseline-${digest}` || baseline.target_id !== 'bank-lab' ||
    baseline.source_mode !== 'isolated-live-bank' || baseline.origin_ref !== 'disposable-loopback-3001' ||
    baseline.scenario_version !== 'baseline-v1' || !/^[a-f0-9-]{36}$/.test(baseline.run_id ?? '') ||
    !Array.isArray(baseline.samples) || baseline.samples.length !== 6 ||
    baseline.samples.some(sample => sample.status !== 200 || !Number.isFinite(sample.latency_ms) ||
      sample.latency_ms < 0 || sample.latency_ms > 200)) {
  throw new Error('Measured disposable bank baseline is missing or unsuitable');
}
const age = Date.now() - Date.parse(baseline.sampled_at);
if (!Number.isFinite(age) || age < 0 || age > 30 * 60_000) {
  throw new Error('Disposable bank baseline is stale');
}
const source = readFileSync(envPath, 'utf8');
if (!/^BANK_SCENARIO=baseline$/m.test(source) || source.includes('BANK_AVAILABILITY_APPROVAL_ID=')) {
  throw new Error('Disposable bank environment is not at its baseline stage');
}
const approval = validateApproval({
  approvalId: `desktop-${digest}`, scope: 'isolated-lab', runId: baseline.run_id,
  scenarioVersion: baseline.scenario_version, baselineEvidenceRefs: [evidenceRef],
  profile: {maxRequests: 30, maxConcurrent: 6, durationMs: 4000,
    requestTimeoutMs: 1000, minIntervalMs: 100, probeRequests: 30, controlRequests: 4},
  criteria: {healthMaxMs: 200, ordinaryMaxMs: 200, recoverySamples: 3, baselineMaxAgeMs: 3000},
});
const bankProfile = {maxRequests: 30, maxConcurrent: 4, durationMs: 4500,
  workMs: 250, degradedAt: 2, mitigationTtlMs: 3000, limitRps: 1, limitBurst: 1};
const staged = {target_id: 'bank-lab', deployment: 'disposable-desktop',
  origin_ref: 'disposable-loopback-3001', source_mode: 'live', approval,
  bank_profile: bankProfile, calibrated_from: evidenceRef,
  status: 'staged-no-load'};
writeFileSync(approvalPath, JSON.stringify(staged, null, 2) + '\n', {flag: 'wx'});
const additions = [
  ['BANK_AVAILABILITY_APPROVAL_ID', approval.approvalId],
  ['BANK_AVAILABILITY_RUN_ID', approval.runId],
  ['BANK_AVAILABILITY_VERSION', approval.scenarioVersion],
  ['BANK_AVAILABILITY_MAX_REQUESTS', bankProfile.maxRequests],
  ['BANK_AVAILABILITY_MAX_CONCURRENT', bankProfile.maxConcurrent],
  ['BANK_AVAILABILITY_DURATION_MS', bankProfile.durationMs],
  ['BANK_AVAILABILITY_WORK_MS', bankProfile.workMs],
  ['BANK_AVAILABILITY_DEGRADED_AT', bankProfile.degradedAt],
  ['BANK_AVAILABILITY_MITIGATION_TTL_MS', bankProfile.mitigationTtlMs],
  ['BANK_AVAILABILITY_LIMIT_RPS', bankProfile.limitRps],
  ['BANK_AVAILABILITY_LIMIT_BURST', bankProfile.limitBurst],
].map(([key, value]) => `${key}=${value}`);
writeFileSync(envPath, source.replace(/^BANK_SCENARIO=baseline$/m, 'BANK_SCENARIO=availability-training').trimEnd() +
  '\n' + additions.join('\n') + '\n');
console.log(JSON.stringify(staged));
