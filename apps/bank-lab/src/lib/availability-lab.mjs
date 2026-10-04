import {createHash, randomUUID, timingSafeEqual} from 'node:crypto';

// Engineering ceilings for the synthetic capacity exercise. These are not an
// approved traffic profile; every enabled instance needs an explicit profile.
const CEILINGS = Object.freeze({maxRequests: 60, maxConcurrent: 12, durationMs: 10_000,
  workMs: 250, degradedAt: 12, mitigationTtlMs: 10_000});
// Keep even a full history comfortably inside the adapter's 16 KiB response cap.
const MAX_TRANSITIONS = 64;
const TOKEN = /^[a-f0-9]{64}$/;
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$/;
const RUN_ID = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const digest = value => createHash('sha256').update(value).digest();

function plainData(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) return false;
  return Reflect.ownKeys(value).every(key => typeof key === 'string' &&
    Object.hasOwn(Object.getOwnPropertyDescriptor(value, key), 'value'));
}

function exactKeys(value, keys) {
  return plainData(value) && Reflect.ownKeys(value).length === keys.length &&
    keys.every(key => Object.hasOwn(value, key));
}

function validateConfiguration(approval, profile, credentials) {
  if (!plainData(approval) || typeof approval.approvalId !== 'string' ||
      !IDENTIFIER.test(approval.approvalId) || typeof approval.runId !== 'string' ||
      !RUN_ID.test(approval.runId) || typeof approval.scenarioVersion !== 'string' ||
      !IDENTIFIER.test(approval.scenarioVersion)) {
    throw new TypeError('Availability approval configuration is invalid');
  }
  if (!plainData(profile) || Object.entries(CEILINGS).some(([key, ceiling]) =>
    !Number.isSafeInteger(profile[key]) || profile[key] < 1 || profile[key] > ceiling) ||
      profile.maxConcurrent > profile.maxRequests || profile.degradedAt > profile.maxConcurrent ||
      profile.workMs > profile.durationMs) {
    throw new RangeError('Availability profile is invalid');
  }
  if (!plainData(credentials) || ['load', 'probe', 'executor'].some(key =>
    typeof credentials[key] !== 'string' || !TOKEN.test(credentials[key])) ||
      new Set([credentials.load, credentials.probe, credentials.executor]).size !== 3) {
    throw new TypeError('Availability credential configuration is invalid');
  }
}

export class AvailabilityLab {
  #enabled;
  #approval;
  #profile;
  #credentials;
  #exerciseId = randomUUID();
  #pending = new Map();
  #admitted = 0;
  #completed = 0;
  #startedAt = null;
  #deadlineTimer = null;
  #stopped = false;
  #limiterExpiresAt = 0;
  #limitRate;
  #limitBurst;
  #limitTokens = 0;
  #limitUpdatedAt = 0;
  #policyRevision = 0;
  #limitRejections = 0;
  #measurements = [];
  #measurementLost = false;
  #measurementStart = performance.now();
  #transitions = [];
  #sequence = 0;

  constructor({enabled = false, approval, profile, credentials, mitigation = {ratePerSecond: 1, burst: 1}} = {}) {
    if (typeof enabled !== 'boolean') throw new TypeError('Availability enablement is invalid');
    this.#enabled = enabled;
    if (!enabled) return;
    validateConfiguration(approval, profile, credentials);
    if (!exactKeys(mitigation, ['ratePerSecond', 'burst']) ||
        !Number.isSafeInteger(mitigation.ratePerSecond) || mitigation.ratePerSecond < 1 || mitigation.ratePerSecond > 10 ||
        !Number.isSafeInteger(mitigation.burst) || mitigation.burst < 1 || mitigation.burst > 10) {
      throw new RangeError('Availability mitigation is invalid');
    }
    this.#limitRate = mitigation.ratePerSecond;
    this.#limitBurst = mitigation.burst;
    this.#approval = Object.freeze({approvalId: approval.approvalId, runId: approval.runId,
      scenarioVersion: approval.scenarioVersion});
    this.#profile = Object.freeze(Object.fromEntries(Object.keys(CEILINGS).map(key => [key, profile[key]])));
    this.#credentials = Object.freeze({
      'load-demo': digest(credentials.load), 'referee-probe': digest(credentials.probe),
      'core-executor': digest(credentials.executor),
    });
    this.#recordTransition(true);
  }

  #authenticate(authorization) {
    const valid = typeof authorization === 'string' && authorization.length === 71 &&
      authorization.startsWith('Bearer ') && TOKEN.test(authorization.slice(7));
    const supplied = digest(valid ? authorization.slice(7) : 'invalid');
    let reference = null;
    // Compare each fixed-length private digest, even after a match.
    for (const [clientRef, expected] of Object.entries(this.#credentials)) {
      if (timingSafeEqual(supplied, expected) && valid) reference = clientRef;
    }
    return reference;
  }

  #label() {
    return this.#pending.size >= this.#profile.degradedAt ? 'degraded' : 'available';
  }

  #recordTransition(force = false) {
    const status = this.#label();
    const previous = this.#transitions.at(-1);
    if (!force && previous?.status === status) return;
    this.#transitions.push({sequence: ++this.#sequence, timestamp: new Date().toISOString(),
      exercise_id: this.#exerciseId, status, active: this.#pending.size});
    if (this.#transitions.length > MAX_TRANSITIONS) this.#transitions.splice(0, this.#transitions.length - MAX_TRANSITIONS);
  }

  #sync() {
    const now = performance.now();
    if (this.#limiterExpiresAt <= now) this.#limiterExpiresAt = 0;
    if (this.#limiterExpiresAt > now) {
      this.#limitTokens = Math.min(this.#limitBurst,
        this.#limitTokens + (now - this.#limitUpdatedAt) * this.#limitRate / 1000);
      this.#limitUpdatedAt = now;
    }
    if (!this.#stopped && this.#startedAt !== null &&
        now - this.#startedAt >= this.#profile.durationMs) this.#stop();
  }

  #snapshot() {
    const accepting = !this.#stopped && this.#admitted < this.#profile.maxRequests &&
      this.#pending.size < this.#profile.maxConcurrent && (this.#limiterExpiresAt === 0 || this.#limitTokens >= 1);
    return {target_id: 'bank-lab', run_id: this.#approval.runId,
      scenario_version: this.#approval.scenarioVersion, exercise_id: this.#exerciseId,
      source: 'availability-training', status: this.#label(), active: this.#pending.size,
      max_active: this.#profile.maxConcurrent, degraded_at: this.#profile.degradedAt,
      admitted: this.#admitted, completed: this.#completed,
      remaining_requests: this.#profile.maxRequests - this.#admitted,
      accepting_work: accepting, rate_limited: this.#limiterExpiresAt > 0,
      policy_revision: this.#policyRevision, limit_rejections: this.#limitRejections,
      limit_rate: this.#limitRate, limit_burst: this.#limitBurst, limit_ttl_ms: this.#profile.mitigationTtlMs,
      transitions: this.#transitions.map(row => ({...row}))};
  }

  #window() {
    // Target-side aggregate measurements, never reconstructed from Red claims.
    // Only the fixed registered load credential can produce this source.
    const now = performance.now();
    const rows = this.#measurements.filter(row => row.started >= now - 500);
    const latencies = rows.filter(row => row.finished !== null).map(row => row.finished - row.started).sort((a, b) => a - b);
    const source = {source_ref: 'load-demo', requests: rows.length,
      backend_requests: rows.filter(row => row.admitted).length,
      server_errors: rows.filter(row => row.status >= 500).length,
      denied_requests: rows.filter(row => !row.admitted).length, inflight: this.#pending.size};
    return {window_id: 'window-' + randomUUID(), seconds: Math.max(.1, Math.min(500, now - this.#measurementStart) / 1000),
      ...Object.fromEntries(Object.entries(source).filter(([key]) => key !== 'source_ref')),
      latency_p95_ms: latencies.length ? latencies[Math.ceil(latencies.length * .95) - 1] : null,
      data_loss: this.#measurementLost, sources: [source]};
  }

  #finish(workId, cancelled) {
    const work = this.#pending.get(workId);
    if (!work) return;
    clearTimeout(work.timer);
    this.#pending.delete(workId);
    work.measurement.status = cancelled ? 409 : 200;
    work.measurement.finished = performance.now();
    if (!cancelled) this.#completed += 1;
    this.#recordTransition();
    work.resolve({status: cancelled ? 409 : 200,
      body: {...this.#snapshot(), ...(cancelled ? {error: 'Availability work cancelled'} : {})}});
  }

  #stop() {
    this.#stopped = true;
    clearTimeout(this.#deadlineTimer);
    this.#deadlineTimer = null;
    for (const workId of [...this.#pending.keys()]) this.#finish(workId, true);
  }

  #work() {
    const measurement = {started: performance.now(), finished: null, admitted: false, status: 0};
    // Every authorized work attempt is bounded at target admission as well as
    // core dispatch. Retain the entire <=60 attempt history; never silently drop.
    if (this.#measurements.length >= 60) {
      this.#stop();
      this.#measurementLost = true;
      measurement.status = 429; measurement.finished = performance.now();
      return {status: 429, body: {...this.#snapshot(), refusal_reason: 'budget'}};
    }
    this.#measurements.push(measurement);
    if (!this.#snapshot().accepting_work) {
      // A policy refusal proves causality only when quota and capacity would
      // otherwise admit this item. Generic denial must not inflate this count.
      const limited = !this.#stopped && this.#admitted < this.#profile.maxRequests &&
        this.#pending.size < this.#profile.maxConcurrent && this.#limiterExpiresAt > 0 && this.#limitTokens < 1;
      if (limited) this.#limitRejections++;
      measurement.status = 429; measurement.finished = performance.now();
      return {status: 429, body: {...this.#snapshot(), refusal_reason: limited ? 'rate_limit' : 'capacity', error: 'Work admission unavailable'}};
    }
    if (this.#limiterExpiresAt > 0) this.#limitTokens -= 1;
    measurement.admitted = true;
    if (this.#startedAt === null) {
      this.#startedAt = performance.now();
      this.#deadlineTimer = setTimeout(() => this.#stop(), this.#profile.durationMs);
      this.#deadlineTimer.unref();
    }
    this.#admitted += 1;
    return new Promise(resolve => {
      const workId = randomUUID();
      const timer = setTimeout(() => {
        this.#sync();
        this.#finish(workId, false);
      }, this.#profile.workMs);
      this.#pending.set(workId, {timer, resolve, measurement});
      this.#recordTransition();
    });
  }

  #control(input) {
    if (!plainData(input)) return {status: 400, body: {error: 'Invalid availability control'}};
    if (input.action === 'limit_load' || input.action === 'restore') {
      if (!exactKeys(input, ['action', 'client_ref']) || input.client_ref !== 'load-demo') {
        return {status: 400, body: {error: 'Invalid availability control'}};
      }
      this.#limiterExpiresAt = input.action === 'limit_load'
        ? performance.now() + this.#profile.mitigationTtlMs : 0;
      this.#policyRevision++;
      this.#limitTokens = 0;
      this.#limitUpdatedAt = performance.now();
    } else if (input.action === 'stop') {
      if (!exactKeys(input, ['action'])) return {status: 400, body: {error: 'Invalid availability control'}};
      this.#stop();
    } else if (input.action === 'reset') {
      if (!exactKeys(input, ['action'])) return {status: 400, body: {error: 'Invalid availability control'}};
      if (this.#pending.size !== 0) return {status: 409, body: {error: 'Availability work is active'}};
      clearTimeout(this.#deadlineTimer);
      this.#deadlineTimer = null;
      this.#exerciseId = randomUUID();
      this.#admitted = 0;
      this.#completed = 0;
      this.#startedAt = null;
      this.#stopped = false;
      this.#limiterExpiresAt = 0;
      this.#policyRevision = 0;
      this.#limitRejections = 0;
      this.#measurements = [];
      this.#measurementLost = false;
      this.#measurementStart = performance.now();
      this.#recordTransition(true);
    } else {
      return {status: 400, body: {error: 'Invalid availability control'}};
    }
    return {status: 200, body: {...this.#snapshot(), applied: true}};
  }

  // The HTTP layer can reject an unauthorized request before it reads bank state.
  // This checks only the fixed credential/capability boundary and never touches work.
  authorize({method, operation, authorization} = {}) {
    if (!this.#enabled) return {status: 404, body: {error: 'Route not found'}};
    const clientRef = this.#authenticate(authorization);
    if (!clientRef) return {status: 401, body: {error: 'Availability authorization required'}};
    const expected = {status: ['GET', 'referee-probe'], work: ['POST', 'load-demo'],
      control: ['POST', 'core-executor']}[operation];
    if (!expected) return {status: 404, body: {error: 'Route not found'}};
    if (method !== expected[0]) return {status: 405, body: {error: 'Method not allowed'}};
    if (clientRef !== expected[1]) return {status: 403, body: {error: 'Availability capability denied'}};
    return null;
  }

  /** @param {{method?: string, operation?: string, authorization?: string | null,
   * input?: Record<string, unknown>, bankState?: Record<string, unknown>}} request */
  /**
   * @param {{method?: string, operation?: string, authorization?: string,
   * input?: unknown, bankState?: {run_id: string, scenario_version: string},
   * expectedExerciseId?: string}} request
   * @returns {Promise<{status: number, body: Record<string, unknown>}>}
   */
  async handle({method, operation, authorization, input = {}, bankState, expectedExerciseId} = {}) {
    const denial = this.authorize({method, operation, authorization});
    if (denial) return denial;
    if (!plainData(bankState) || bankState.run_id !== this.#approval.runId ||
        bankState.scenario_version !== this.#approval.scenarioVersion) {
      this.#stop();
      return {status: 409, body: {error: 'Availability approval does not match bank state'}};
    }
    if (operation !== 'status' && (typeof expectedExerciseId !== 'string' ||
        expectedExerciseId !== this.#exerciseId)) {
      return {status: 409, body: {error: 'Availability exercise does not match'}};
    }
    this.#sync();
    try {
      if (operation === 'control') return this.#control(input);
      if (!exactKeys(input, [])) return {status: 400, body: {error: 'Availability input must be empty'}};
      if (operation === 'status') return {status: 200, body: {...this.#snapshot(), window: this.#window()}};
      return this.#work();
    } catch {
      return {status: 400, body: {error: 'Invalid availability input'}};
    }
  }
}

export function createAvailabilityLabFromEnv(env = process.env) {
  try {
    if (env.BANK_SCENARIO !== 'availability-training') return new AvailabilityLab();
    const readNumber = suffix => {
      const raw = env[`BANK_AVAILABILITY_${suffix}`];
      if (typeof raw !== 'string' || !/^[1-9]\d{0,4}$/.test(raw)) throw new RangeError('Invalid profile');
      return Number(raw);
    };
    return new AvailabilityLab({enabled: true, approval: {
      approvalId: env.BANK_AVAILABILITY_APPROVAL_ID,
      runId: env.BANK_AVAILABILITY_RUN_ID,
      scenarioVersion: env.BANK_AVAILABILITY_VERSION,
    }, profile: {
      maxRequests: readNumber('MAX_REQUESTS'), maxConcurrent: readNumber('MAX_CONCURRENT'),
      durationMs: readNumber('DURATION_MS'), workMs: readNumber('WORK_MS'),
      degradedAt: readNumber('DEGRADED_AT'), mitigationTtlMs: readNumber('MITIGATION_TTL_MS'),
    }, mitigation: {ratePerSecond: readNumber('LIMIT_RPS'), burst: readNumber('LIMIT_BURST')}, credentials: {
      load: env.BANK_AVAILABILITY_LOAD_TOKEN, probe: env.BANK_AVAILABILITY_PROBE_TOKEN,
      executor: env.BANK_AVAILABILITY_EXECUTOR_TOKEN,
    }});
  } catch {
    // Missing, malformed, or incomplete approvals never turn on a demo route.
    return new AvailabilityLab();
  }
}
