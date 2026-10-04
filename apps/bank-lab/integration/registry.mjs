import {Server} from 'node:http';

// Engineering ceilings only. A bank run still requires its own measured approval.
export const HARD_LIMITS = Object.freeze({
  maxRequests: 60, maxConcurrent: 12, durationMs: 10_000,
  requestTimeoutMs: 5_000, minIntervalMs: 10_000, probeRequests: 30, controlRequests: 4,
  responseBytes: 16_384,
  baselineMaxAgeMs: 10_000,
});
const ORIGINS = Object.freeze({desktop: 'http://127.0.0.1:3000',
  'disposable-desktop': 'http://127.0.0.1:3001', docker: 'http://bank:3000'});
const OPERATIONS = Object.freeze({
  health: ['GET', '/api/health'], ordinary: ['GET', '/api/accounts'],
  status: ['GET', '/api/availability/status'], work: ['POST', '/api/availability/work'],
  control: ['POST', '/api/availability/control'],
});
const FIXTURE = Symbol('trusted disposable server');
export class IntegrationPolicyError extends Error {}
export function safeRef(value) {
  return typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(value);
}
function exactKeys(value, keys) {
  return value && Object.getPrototypeOf(value) === Object.prototype &&
    Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
export function validateApproval(value) {
  const fields = ['approvalId', 'scope', 'runId', 'scenarioVersion', 'baselineEvidenceRefs', 'profile', 'criteria'];
  if (!exactKeys(value, fields) || value.scope !== 'isolated-lab' ||
      ![value.approvalId, value.runId, value.scenarioVersion].every(safeRef) ||
      !Array.isArray(value.baselineEvidenceRefs) || value.baselineEvidenceRefs.length < 1 ||
      value.baselineEvidenceRefs.length > 8 || !value.baselineEvidenceRefs.every(safeRef)) {
    throw new IntegrationPolicyError('A measured, scoped approval is required');
  }
  const {profile, criteria} = value;
  const names = ['maxRequests', 'maxConcurrent', 'durationMs', 'requestTimeoutMs', 'minIntervalMs', 'probeRequests', 'controlRequests'];
  if (!exactKeys(profile, names) || names.some(key => !Number.isSafeInteger(profile[key]) ||
      profile[key] < 1 || profile[key] > HARD_LIMITS[key]) || profile.maxConcurrent < 3 ||
      profile.maxConcurrent > profile.maxRequests + 2 || profile.requestTimeoutMs > profile.durationMs ||
      profile.controlRequests < 2 || profile.minIntervalMs > profile.durationMs) {
    throw new IntegrationPolicyError('Invalid bounded profile');
  }
  if (!exactKeys(criteria, ['healthMaxMs', 'ordinaryMaxMs', 'recoverySamples', 'baselineMaxAgeMs']) ||
      ![criteria.healthMaxMs, criteria.ordinaryMaxMs].every(n => Number.isFinite(n) && n > 0 && n <= profile.requestTimeoutMs) ||
      !Number.isSafeInteger(criteria.baselineMaxAgeMs) || criteria.baselineMaxAgeMs < 1 || criteria.baselineMaxAgeMs > HARD_LIMITS.baselineMaxAgeMs ||
      !Number.isSafeInteger(criteria.recoverySamples) || criteria.recoverySamples < 1 || criteria.recoverySamples > 5) {
    throw new IntegrationPolicyError('Invalid measured verification criteria');
  }
  return Object.freeze({...value, profile: Object.freeze({...profile}), criteria: Object.freeze({...criteria}),
    baselineEvidenceRefs: Object.freeze([...value.baselineEvidenceRefs])});
}

class FixedBankRegistry {
  #origin; #approval; #targetId; #sourceMode;
  constructor({deployment = 'desktop', approval = null} = {}, fixture) {
    if (!Object.hasOwn(ORIGINS, deployment)) throw new IntegrationPolicyError('Unknown deployment');
    this.#origin = ORIGINS[deployment];
    this.#targetId = 'bank-lab';
    this.#sourceMode = 'live';
    if (fixture?.key === FIXTURE) {
      this.#origin = fixture.origin;
      this.#targetId = 'availability-fixture';
      this.#sourceMode = 'fixture';
    }
    this.#approval = approval === null ? null : validateApproval(approval);
    Object.freeze(this);
  }
  describe() {
    return Object.freeze({target_id: this.#targetId, bank_target_id: 'bank-lab',
      scenario_id: 'availability-training', source_mode: this.#sourceMode,
      traffic_enabled: this.#approval !== null, capabilities: Object.keys(OPERATIONS)});
  }
  resolve(targetId, operation) {
    if (targetId !== this.#targetId) throw new IntegrationPolicyError('Unknown registered target');
    if (!Object.hasOwn(OPERATIONS, operation)) throw new IntegrationPolicyError('Unregistered capability');
    if (!this.#approval) throw new IntegrationPolicyError('Target traffic is not approved');
    const [method, path] = OPERATIONS[operation];
    return Object.freeze({targetId, bankTargetId: 'bank-lab', method, path,
      origin: this.#origin, sourceMode: this.#sourceMode, approval: this.#approval});
  }
}
export function createBankRegistry(options = {}) {
  if (!options || Object.keys(options).some(key => !['deployment', 'approval'].includes(key))) {
    throw new IntegrationPolicyError('Registry options are operator-only and fixed');
  }
  return new FixedBankRegistry(options);
}
export function createDisposableRegistry(server, approval) {
  const address = server instanceof Server && server.listening ? server.address() : null;
  if (!address || typeof address === 'string' || address.address !== '127.0.0.1' ||
      address.port < 1024 || address.port === 3000) {
    throw new IntegrationPolicyError('An owned, listening disposable loopback server is required');
  }
  return new FixedBankRegistry({approval}, {key: FIXTURE, origin: `http://127.0.0.1:${address.port}`});
}
export function requireRegistry(value) {
  if (!(value instanceof FixedBankRegistry)) throw new IntegrationPolicyError('A fixed registry is required');
  return value;
}
