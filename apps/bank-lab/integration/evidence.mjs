import {createHash} from 'node:crypto';
import {appendFileSync, closeSync, fsyncSync, mkdirSync, openSync} from 'node:fs';
import {join} from 'node:path';
import {safeRef} from './registry.mjs';

const FIELDS = Object.freeze({
  'target.health': ['kind', 'status', 'latency_ms', 'http_status', 'client_ref', 'run_id', 'scenario_version',
    'exercise_id', 'active', 'degraded_at', 'error', 'policy_revision', 'limit_rejections', 'rate_limited', 'limit_rate', 'limit_burst', 'limit_ttl_ms'],
  'availability.load_started': ['load_id', 'status', 'dispatched', 'completed', 'exercise_id', 'run_id',
    'scenario_version', 'approval_ref', 'max_requests'],
  'availability.load_finished': ['load_id', 'status', 'dispatched', 'completed', 'remote_stop'],
  'availability.work_started': ['load_id', 'request_id', 'status'],
  'availability.work_observed': ['load_id', 'request_id', 'status', 'http_status', 'client_ref', 'run_id',
    'scenario_version', 'exercise_id', 'error', 'refusal_reason'],
  'defense.applied': ['defense_id', 'client_ref', 'status', 'exercise_id', 'policy_revision', 'limit_rate', 'limit_burst', 'limit_ttl_ms'],
});
const METRICS = new Set(['latency_ms', 'http_status', 'active', 'degraded_at', 'dispatched', 'completed', 'max_requests',
  'policy_revision', 'limit_rejections', 'rate_limited', 'limit_rate', 'limit_burst', 'limit_ttl_ms']);
const ENUMS = {
  kind: ['health', 'status', 'ordinary'],
  status: ['available', 'degraded', 'unavailable', 'inconclusive', 'started', 'completed', 'cancelled', 'deadline', 'applied', 'rejected', 'shed'],
  error: ['cancelled', 'redirect_rejected', 'response_too_large', 'transport_error', 'timeout', 'invalid_response', 'identity_mismatch'],
  remote_stop: ['applied', 'rejected'],
  refusal_reason: ['rate_limit'],
};

// This is an injectable core handoff ledger, not a new public control-plane API.
// Only typed metadata is persisted; bank reset cannot erase this file.
export class EvidenceLedger {
  #entries = []; #fd = null; #sessionId; #targetId; #sourceMode; #closed = false;
  constructor({sessionId, targetId, sourceMode, directory} = {}) {
    if (![sessionId, targetId].every(safeRef) || !['fixture', 'live'].includes(sourceMode)) throw new Error('Invalid evidence scope');
    this.#sessionId = sessionId; this.#targetId = targetId; this.#sourceMode = sourceMode;
    if (directory) {
      mkdirSync(directory, {recursive: true});
      this.#fd = openSync(join(directory, `${sessionId}.jsonl`), 'wx');
    }
  }
  scope() { return {sessionId: this.#sessionId, targetId: this.#targetId, sourceMode: this.#sourceMode}; }
  record(eventType, data) {
    if (this.#closed || this.#entries.length >= 256) throw new Error('Evidence ledger closed or full');
    const allowed = FIELDS[eventType];
    if (!allowed || !data || Object.keys(data).some(key => !allowed.includes(key))) throw new Error('Invalid evidence fields');
    for (const [key, value] of Object.entries(data)) {
      if (ENUMS[key]) {
        if (!ENUMS[key].includes(value)) throw new Error('Invalid evidence enum');
      } else if (METRICS.has(key)) {
        if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 ||
            (key !== 'latency_ms' && !Number.isSafeInteger(value))) throw new Error('Invalid evidence metric');
      } else if (!safeRef(value)) throw new Error('Invalid evidence reference');
    }
    const envelope = {sequence: this.#entries.length + 1, session_id: this.#sessionId,
      target_id: this.#targetId, source_mode: this.#sourceMode, event_type: eventType,
      occurred_at: new Date().toISOString(), producer: 'core-bank-adapter', data: {...data}};
    const integrity = createHash('sha256').update(JSON.stringify(envelope)).digest('hex');
    const entry = {...envelope, evidence_id: `ev-${envelope.sequence}-${integrity.slice(0, 16)}`, integrity_sha256: integrity};
    if (this.#fd !== null) { appendFileSync(this.#fd, `${JSON.stringify(entry)}\n`); fsyncSync(this.#fd); }
    this.#entries.push(entry);
    return structuredClone(entry);
  }
  entries() { return structuredClone(this.#entries); }
  close() { if (this.#fd !== null) { closeSync(this.#fd); this.#fd = null; } this.#closed = true; }
}

export function assessRecovery(entries, {loadId, criteria, requirePolicyRefusals = false, requiredPolicy} = {}) {
  const inconclusive = () => ({objective: 'availability-recovery', result: 'inconclusive', evidence_refs: []});
  if (!Array.isArray(entries) || !safeRef(loadId) || !criteria || !Number.isInteger(criteria.recoverySamples) ||
      criteria.recoverySamples < 1 || criteria.recoverySamples > 5 ||
      ![criteria.healthMaxMs, criteria.ordinaryMaxMs, criteria.baselineMaxAgeMs].every(n => Number.isFinite(n) && n > 0)) return inconclusive();
  for (let index = 0; index < entries.length; index++) {
    const entry = entries[index];
    if (!entry || entry.sequence !== index + 1 || !entry.data || !Number.isFinite(Date.parse(entry.occurred_at))) return inconclusive();
    const {evidence_id, integrity_sha256, ...envelope} = entry;
    const hash = createHash('sha256').update(JSON.stringify(envelope)).digest('hex');
    if (hash !== integrity_sha256 || evidence_id !== `ev-${entry.sequence}-${hash.slice(0, 16)}`) return inconclusive();
  }
  const start = entries.find(e => e.event_type === 'availability.load_started' && e.data.load_id === loadId);
  if (!start || start.data.status !== 'started' || !safeRef(start.data.exercise_id) ||
      !safeRef(start.data.run_id) || !safeRef(start.data.scenario_version) || !safeRef(start.data.approval_ref) ||
      !Number.isSafeInteger(start.data.max_requests) || start.data.max_requests < 1 || start.data.max_requests > 60) return inconclusive();
  const scoped = entries.filter(e => e.session_id === start.session_id && e.target_id === start.target_id &&
    e.source_mode === start.source_mode && e.producer === 'core-bank-adapter');
  const end = scoped.find(e => e.event_type === 'availability.load_finished' && e.data.load_id === loadId &&
    e.sequence > start.sequence && ['completed', 'cancelled', 'deadline'].includes(e.data.status) &&
    Number.isSafeInteger(e.data.dispatched) && e.data.dispatched > 0 && e.data.dispatched <= start.data.max_requests &&
    e.data.completed === e.data.dispatched && e.data.remote_stop === 'applied');
  if (!end) return inconclusive();
  const health = scoped.filter(e => e.event_type === 'target.health');
  const sameRun = data => data.run_id === start.data.run_id && data.scenario_version === start.data.scenario_version &&
    data.exercise_id === start.data.exercise_id;
  const validAvailable = event => {
    const data = event.data;
    if (data.status !== 'available' || data.http_status !== 200 || !sameRun(data)) return false;
    if (data.kind === 'status') return Number.isSafeInteger(data.active) && Number.isSafeInteger(data.degraded_at) &&
      data.active >= 0 && data.degraded_at > data.active;
    return Number.isFinite(data.latency_ms) && data.latency_ms >= 0 &&
      data.latency_ms <= (data.kind === 'health' ? criteria.healthMaxMs : criteria.ordinaryMaxMs);
  };
  const baseline = ['status', 'health', 'ordinary'].map(kind => health.findLast(e =>
    e.sequence < start.sequence && e.data.kind === kind));
  if (baseline.some(e => !e || !validAvailable(e) || Date.parse(start.occurred_at) - Date.parse(e.occurred_at) < 0 ||
      Date.parse(start.occurred_at) - Date.parse(e.occurred_at) > criteria.baselineMaxAgeMs)) return inconclusive();
  const degraded = health.find(e => e.sequence > start.sequence && e.sequence < end.sequence &&
    e.data.kind === 'status' && e.data.status === 'degraded' && sameRun(e.data) && e.data.http_status === 200 &&
    Number.isSafeInteger(e.data.active) && Number.isSafeInteger(e.data.degraded_at) &&
    e.data.degraded_at > 0 && e.data.active >= e.data.degraded_at);
  const applied = scoped.find(e => e.event_type === 'defense.applied' && e.data.status === 'applied' &&
    e.sequence > (degraded?.sequence ?? Infinity) && e.sequence < end.sequence);
  if (!degraded || !applied || applied.data.client_ref !== 'load-demo' ||
      applied.data.exercise_id !== start.data.exercise_id) return inconclusive();
  const activeHealth = health.filter(e => e.sequence > start.sequence);
  if (activeHealth.some(e => !sameRun(e.data) || ['inconclusive', 'unavailable'].includes(e.data.status))) return inconclusive();
  // Verification must form a successful window after the last degraded sample;
  // earlier success cannot hide a later regression.
  const lastDegraded = activeHealth.findLast(e => e.sequence < end.sequence && e.data.status === 'degraded');
  const windowStart = Math.max(applied.sequence, lastDegraded?.sequence ?? 0);
  const during = activeHealth.filter(e => e.sequence > windowStart && e.sequence < end.sequence);
  if (during.some(e => !validAvailable(e))) return inconclusive();
  const recovered = during.filter(e => e.data.kind === 'status');
  const ordinary = during.filter(e => e.data.kind === 'ordinary');
  const ready = during.filter(e => e.data.kind === 'health');
  const after = health.find(e => e.sequence > end.sequence && e.data.kind === 'status' &&
    validAvailable(e));
  if (recovered.length < criteria.recoverySamples || ordinary.length < criteria.recoverySamples ||
      ready.length < criteria.recoverySamples || !after ||
      activeHealth.some(e => e.sequence > end.sequence && !validAvailable(e))) return inconclusive();
  const requests = scoped.filter(e => e.event_type === 'availability.work_started' && e.data.load_id === loadId);
  const outcomes = scoped.filter(e => e.event_type === 'availability.work_observed' && e.data.load_id === loadId);
  if (requests.length !== end.data.dispatched || outcomes.length !== end.data.completed ||
      new Set(requests.map(e => e.data.request_id)).size !== requests.length ||
      new Set(outcomes.map(e => e.data.request_id)).size !== outcomes.length ||
      outcomes.some(e => !sameRun(e.data) || e.data.status === 'inconclusive' ||
        !['completed', 'shed', 'cancelled'].includes(e.data.status) ||
        !requests.some(request => request.data.request_id === e.data.request_id && request.sequence > start.sequence &&
          request.sequence < e.sequence && e.sequence < end.sequence))) return inconclusive();
  const validWork = outcomes.filter(e => e.data.client_ref === 'load-demo' &&
    ((e.data.status === 'completed' && e.data.http_status === 200) || (e.data.status === 'shed' && e.data.http_status === 429)));
  // Actual validated load responses must bracket the successful probe window,
  // and a new request must start after the last probe. An open worker or cooldown
  // alone cannot establish continuing load.
  const firstProbe = during[0].sequence, lastProbe = during.at(-1).sequence;
  const beforeWork = validWork.find(e => e.sequence > windowStart && e.sequence < firstProbe);
  const afterWork = validWork.find(e => requests.some(request => request.data.request_id === e.data.request_id &&
    request.sequence > lastProbe));
  if (!beforeWork || !afterWork) return inconclusive();
  if (requirePolicyRefusals) {
    if (!Number.isSafeInteger(applied.data.policy_revision) || applied.data.policy_revision < 1) return inconclusive();
    const verified = recovered.slice(-criteria.recoverySamples);
    let previous = recovered.findLast(e => e.sequence < verified[0].sequence) ?? applied;
    const matchesPolicy = data => !requiredPolicy || (data.limit_rate === requiredPolicy.rate &&
      data.limit_burst === requiredPolicy.burst && data.limit_ttl_ms === requiredPolicy.ttlMs);
    if (!matchesPolicy(applied.data)) return inconclusive();
    for (const sample of verified) {
      const elapsed = (Date.parse(sample.occurred_at) - Date.parse(previous.occurred_at)) / 1000;
      const count = sample.data.limit_rejections - (previous.data.limit_rejections ?? 0);
      if (sample.data.rate_limited !== 1 || sample.data.policy_revision !== applied.data.policy_revision ||
          !matchesPolicy(sample.data) || !Number.isSafeInteger(sample.data.limit_rejections) || count <= 0 ||
          elapsed <= 0 || (requiredPolicy && count / elapsed <= requiredPolicy.suspectRps)) return inconclusive();
      previous = sample;
    }
    if (!validWork.some(e => e.sequence > windowStart && e.data.refusal_reason === 'rate_limit')) return inconclusive();
  }
  return {objective: 'availability-recovery', result: 'achieved',
    evidence_refs: [...baseline, degraded, applied, beforeWork, ...during, afterWork, end, after].map(e => e.evidence_id)};
}
