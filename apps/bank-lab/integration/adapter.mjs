import {randomUUID} from 'node:crypto';
import {setTimeout as delay} from 'node:timers/promises';
import {createBankRegistry, requireRegistry, safeRef, IntegrationPolicyError} from './registry.mjs';
import {boundedRequest} from './transport.mjs';
import {EvidenceLedger} from './evidence.mjs';

const TOKEN = /^[a-f0-9]{64}$/;
const CAPABILITIES = Object.freeze({start_load_test: 'start', stop_load_test: 'stop',
  'availability.load': 'start', 'availability.stop': 'stop'});

// An embeddable adapter for core. Models receive only dispatch(); bootstrap,
// observation, credentials, approved defenses, and the ledger remain trusted.
export class BankAvailabilityAdapter {
  #registry; #credentials; #ledger; #targetId; #transport; #defenses;
  #probeCount = 0; #controlCount = 0; #observerBusy = false; #controlBusy = false;
  #load = null; #completion = null; #exerciseId; #baseline = new Map(); #activeHttp = 0;
  #controlDone = Promise.resolve();
  #paused = false;
  #blueWindow = null;
  constructor({registry = createBankRegistry(), credentials = {}, ledger, approvedDefenseIds = [], transport = boundedRequest} = {}) {
    this.#registry = requireRegistry(registry);
    const description = registry.describe();
    if (!(ledger instanceof EvidenceLedger) || ledger.scope().targetId !== description.target_id ||
        ledger.scope().sourceMode !== description.source_mode || !Array.isArray(approvedDefenseIds) ||
        !approvedDefenseIds.every(safeRef) || typeof transport !== 'function') throw new IntegrationPolicyError('Invalid adapter scope');
    this.#targetId = description.target_id;
    this.#ledger = ledger;
    this.#transport = transport;
    // Copy secret material into private storage; never return it in observations.
    this.#credentials = structuredClone(credentials);
    this.#defenses = new Set(approvedDefenseIds);
  }
  describe() { return this.#registry.describe(); }
  #resolve(operation) { return this.#registry.resolve(this.#targetId, operation); }
  async #request(operation, {body, signal, timeoutMs} = {}) {
    const target = this.#resolve(operation);
    const {profile} = target.approval;
    const headers = {};
    if (operation === 'ordinary') {
      const ordinary = this.#credentials.ordinary;
      if (!ordinary || !TOKEN.test(ordinary.session) || !safeRef(ordinary.ownerId) ||
          !Array.isArray(ordinary.accountIds) || ordinary.accountIds.length < 1 || ordinary.accountIds.length > 10 ||
          !ordinary.accountIds.every(id => typeof id === 'string' && /^\d{4}$/.test(id))) {
        throw new IntegrationPolicyError('Registered ordinary credential reference is required');
      }
      headers.Cookie = `bank_session=${ordinary.session}`;
    } else if (['status', 'work', 'control'].includes(operation)) {
      const key = {status: 'probe', work: 'load', control: 'executor'}[operation];
      const token = this.#credentials[key];
      if (typeof token !== 'string' || !TOKEN.test(token)) throw new IntegrationPolicyError('Registered capability credential is required');
      headers.Authorization = `Bearer ${token}`;
    }
    if (target.method === 'POST') {
      headers['Content-Type'] = 'application/json';
      headers.Origin = target.origin;
      if (!safeRef(this.#exerciseId)) throw new IntegrationPolicyError('A registered exercise pin is required');
      headers['X-Bank-Exercise'] = this.#exerciseId;
    }
    if (signal?.aborted) return {status: 0, body: null, error: 'cancelled', latencyMs: 0};
    if (this.#activeHttp >= profile.maxConcurrent) throw new IntegrationPolicyError('Aggregate concurrency exhausted');
    this.#activeHttp++;
    const started = performance.now();
    try {
      const result = await this.#transport({origin: target.origin, path: target.path, method: target.method,
        headers, body, signal, timeoutMs: timeoutMs ?? profile.requestTimeoutMs});
      return {...result, latencyMs: performance.now() - started};
    } catch {
      return {status: 0, body: null, error: signal?.aborted ? 'cancelled' : 'transport_error', latencyMs: performance.now() - started};
    } finally { this.#activeHttp--; }
  }
  #validSnapshot(body, target) {
    return body && body.target_id === target.bankTargetId && body.run_id === target.approval.runId &&
      body.scenario_version === target.approval.scenarioVersion && body.source === 'availability-training' &&
      safeRef(body.exercise_id) && Number.isSafeInteger(body.active) && body.active >= 0 &&
      Number.isSafeInteger(body.max_active) && body.max_active >= 1 && body.max_active <= 12 && body.active <= body.max_active &&
      Number.isSafeInteger(body.degraded_at) && body.degraded_at >= 1 && body.degraded_at <= body.max_active &&
      body.status === (body.active >= body.degraded_at ? 'degraded' : 'available');
  }
  async observe(kind) {
    if (!['health', 'status', 'ordinary'].includes(kind)) throw new IntegrationPolicyError('Unknown observation');
    const target = this.#resolve(kind);
    if (this.#observerBusy || this.#probeCount >= target.approval.profile.probeRequests) throw new IntegrationPolicyError('Observation budget exhausted or busy');
    this.#observerBusy = true;
    this.#probeCount++;
    try {
      const response = await this.#request(kind);
      const body = response.body;
      const data = {kind, status: 'inconclusive', http_status: response.status || 0,
        latency_ms: Math.round(response.latencyMs * 100) / 100,
        client_ref: kind === 'ordinary' ? 'ordinary-demo' : 'referee-probe',
        run_id: target.approval.runId, scenario_version: target.approval.scenarioVersion};
      if (this.#exerciseId) data.exercise_id = this.#exerciseId;
      const pinned = body && body.run_id === target.approval.runId;
      if (response.error) data.error = response.error;
      else if (kind === 'health') {
        if (body?.target_id !== target.bankTargetId) data.error = 'identity_mismatch';
        else if (response.status === 503 && body.status === 'unavailable') data.status = 'unavailable';
        else if (response.status === 200 && pinned && body.scenario_version === target.approval.scenarioVersion && body.status === 'ready') {
          data.status = response.latencyMs <= target.approval.criteria.healthMaxMs ? 'available' : 'degraded';
        } else data.error = 'invalid_response';
      } else if (kind === 'status') {
        const valid = response.status === 200 && this.#validSnapshot(body, target);
        if (valid) {
          if (this.#exerciseId && body.exercise_id !== this.#exerciseId && this.#load) {
            data.error = 'identity_mismatch';
            if (this.#load.active) { this.#load.reason = 'inconclusive'; this.#load.controller.abort(); }
          } else {
            if (body.exercise_id !== this.#exerciseId) this.#baseline.clear();
            this.#exerciseId = body.exercise_id;
            Object.assign(data, {status: body.status, exercise_id: body.exercise_id, active: body.active, degraded_at: body.degraded_at});
            if (Number.isSafeInteger(body.policy_revision) && Number.isSafeInteger(body.limit_rejections)) {
              Object.assign(data, {policy_revision: body.policy_revision, limit_rejections: body.limit_rejections,
                rate_limited: body.rate_limited === true ? 1 : 0, limit_rate: body.limit_rate,
                limit_burst: body.limit_burst, limit_ttl_ms: body.limit_ttl_ms});
            }
            this.#blueWindow = {window: structuredClone(body.window), at: performance.now(),
              policy: {rate: body.limit_rate, burst: body.limit_burst, ttlMs: body.limit_ttl_ms}};
          }
        } else data.error = 'invalid_response';
      } else {
        const ordinary = this.#credentials.ordinary;
        const accounts = body?.accounts;
        const valid = response.status === 200 && pinned && Array.isArray(accounts) &&
          accounts.length === ordinary.accountIds.length && accounts.every(account =>
            account?.owner_id === ordinary.ownerId && ordinary.accountIds.includes(account.account_id)) &&
          new Set(accounts.map(a => a.account_id)).size === accounts.length;
        if (valid) data.status = response.latencyMs <= target.approval.criteria.ordinaryMaxMs ? 'available' : 'degraded';
        else data.error = 'invalid_response';
      }
      if (!this.#load && this.#exerciseId && data.status === 'available') {
        this.#baseline.set(kind, {at: performance.now(), exerciseId: this.#exerciseId});
      }
      else if (!this.#load) this.#baseline.delete(kind);
      return this.#ledger.record('target.health', data);
    } finally { this.#observerBusy = false; }
  }
  dispatch(proposal) {
    const keys = ['capability', 'target_id', 'path', 'method', 'body', 'identity_ref', 'session_ref', 'form_ref'];
    if (!proposal || Object.getPrototypeOf(proposal) !== Object.prototype || Object.keys(proposal).some(key => !keys.includes(key)) ||
        proposal.target_id !== this.#targetId || !Object.hasOwn(CAPABILITIES, proposal.capability) ||
        (proposal.path !== undefined && proposal.path !== '/') || (proposal.method !== undefined && proposal.method !== 'GET') ||
        (proposal.body !== undefined && (!proposal.body || Object.getPrototypeOf(proposal.body) !== Object.prototype || Object.keys(proposal.body).length)) ||
        ['identity_ref', 'session_ref', 'form_ref'].some(key => proposal[key] !== undefined && proposal[key] !== null)) {
      throw new IntegrationPolicyError('Load actions accept only a registered target and capability');
    }
    this.#resolve('work');
    return CAPABILITIES[proposal.capability] === 'start' ? this.#start() : this.stop();
  }
  #start() {
    const {profile, criteria} = this.#resolve('work').approval;
    const now = performance.now();
    if (this.#load || !['health', 'status', 'ordinary'].every(kind => {
      const sample = this.#baseline.get(kind);
      return Boolean(sample && sample.exerciseId === this.#exerciseId && now - sample.at <= criteria.baselineMaxAgeMs);
    })) {
      throw new IntegrationPolicyError('A fresh healthy baseline and unused load budget are required');
    }
    if (!['load', 'executor'].every(key => typeof this.#credentials[key] === 'string' && TOKEN.test(this.#credentials[key]))) {
      throw new IntegrationPolicyError('Load and executor credential references are required');
    }
    const load = {id: `load-${randomUUID()}`, controller: new AbortController(),
      deadline: performance.now() + profile.durationMs, dispatched: 0, completed: 0, reason: 'completed', active: true};
    const approval = this.#resolve('work').approval;
    this.#ledger.record('availability.load_started', {load_id: load.id, status: 'started', dispatched: 0, completed: 0,
      exercise_id: this.#exerciseId, run_id: approval.runId, scenario_version: approval.scenarioVersion,
      approval_ref: approval.approvalId, max_requests: profile.maxRequests});
    this.#load = load;
    const timer = setTimeout(() => { load.reason = 'deadline'; load.controller.abort(); }, profile.durationMs);
    this.#completion = (async () => {
      const worker = async () => {
        while (!load.controller.signal.aborted && performance.now() < load.deadline && load.dispatched < profile.maxRequests) {
          if (this.#paused) {
            try { await delay(5, undefined, {signal: load.controller.signal}); } catch { /* deadline or stop */ }
            continue;
          }
          // No prequeued work. Reservation and actual dispatch occur without a yield.
          load.dispatched++;
          const requestId = `request-${load.dispatched}`;
          this.#ledger.record('availability.work_started', {load_id: load.id, request_id: requestId, status: 'started'});
          const response = await this.#request('work', {body: {}, signal: load.controller.signal,
            timeoutMs: Math.max(1, Math.min(profile.requestTimeoutMs, Math.ceil(load.deadline - performance.now())))});
          const target = this.#resolve('work');
          const valid = !response.error && this.#validSnapshot(response.body, target) && response.body.exercise_id === this.#exerciseId;
          const outcome = response.error === 'cancelled' ? 'cancelled' : valid && response.status === 200 ? 'completed' :
            valid && response.status === 429 ? 'shed' : 'inconclusive';
          this.#ledger.record('availability.work_observed', {load_id: load.id, request_id: requestId, status: outcome,
            http_status: response.status || 0, client_ref: 'load-demo', run_id: target.approval.runId,
            scenario_version: target.approval.scenarioVersion, exercise_id: this.#exerciseId,
            ...(valid && response.body.refusal_reason === 'rate_limit' ? {refusal_reason: 'rate_limit'} : {}),
            ...(response.error ? {error: response.error} : {})});
          load.completed++;
          if (!load.controller.signal.aborted) {
            try { await delay(profile.minIntervalMs, undefined, {signal: load.controller.signal}); } catch { /* bounded cancellation */ }
          }
        }
      };
      try {
        // Two reserved slots keep the observer and executor available during load.
        const workers = Array.from({length: Math.min(profile.maxConcurrent - 2, profile.maxRequests)}, () => worker().catch(error => {
          load.reason = 'inconclusive'; load.controller.abort(); throw error;
        }));
        const results = await Promise.allSettled(workers);
        await this.#controlDone;
        try { load.stopReceipt = await this.#control('stop'); }
        catch { load.stopReceipt = {status: 'rejected'}; }
        if (results.some(result => result.status === 'rejected')) throw new IntegrationPolicyError('Bounded load evidence unavailable');
        return this.#ledger.record('availability.load_finished', {load_id: load.id, status: load.reason,
          dispatched: load.dispatched, completed: load.completed, remote_stop: load.stopReceipt.status});
      } finally { load.controller.abort(); clearTimeout(timer); load.active = false; }
    })();
    // Observe errors even if a host waits later; wait() still returns the failure.
    this.#completion.catch(() => {});
    return {status: 'started', load_id: load.id, target_id: this.#targetId, source_mode: this.describe().source_mode};
  }
  async #control(action, defenseId) {
    const target = this.#resolve('control');
    const stopping = action === 'stop';
    if (this.#controlBusy || this.#controlCount >= target.approval.profile.controlRequests - (stopping ? 0 : 1)) {
      throw new IntegrationPolicyError('Executor budget exhausted or busy');
    }
    this.#controlBusy = true;
    let controlFinished;
    this.#controlDone = new Promise(resolve => { controlFinished = resolve; });
    this.#controlCount++;
    try {
      const body = ['limit_load', 'restore'].includes(action) ? {action, client_ref: 'load-demo'} : {action};
      const response = await this.#request('control', {body});
      const value = response.body;
      const applied = !response.error && response.status === 200 && value?.target_id === target.bankTargetId &&
        value.run_id === target.approval.runId && value.scenario_version === target.approval.scenarioVersion &&
        value.exercise_id === this.#exerciseId && (value.status === 'applied' || value.applied === true);
      if (defenseId) return this.#ledger.record('defense.applied', {defense_id: defenseId, client_ref: 'load-demo',
        status: applied ? 'applied' : 'rejected', ...(applied && Number.isSafeInteger(value.policy_revision) ? {
          policy_revision: value.policy_revision, limit_rate: value.limit_rate,
          limit_burst: value.limit_burst, limit_ttl_ms: value.limit_ttl_ms} : {}),
        ...(this.#exerciseId ? {exercise_id: this.#exerciseId} : {})});
      return {status: applied ? 'applied' : 'rejected'};
    } finally { this.#controlBusy = false; controlFinished(); }
  }
  applyDefense(defenseId) {
    if (!this.#defenses.has(defenseId)) throw new IntegrationPolicyError('Defense was not approved');
    return this.#control('limit_load', defenseId);
  }
  restoreDefense(defenseId) {
    if (!this.#defenses.has(defenseId)) throw new IntegrationPolicyError('Defense was not approved');
    return this.#control('restore');
  }
  async stop() {
    this.#resolve('control');
    if (!this.#load?.active) return {status: 'not_running'};
    this.#load.reason = 'cancelled';
    this.#load.controller.abort();
    await this.#completion;
    return this.#load.stopReceipt;
  }
  async wait() { return this.#completion ? this.#completion : null; }
  running() { return Boolean(this.#load?.active); }
  async pause() {
    this.#paused = true;
    const deadline = performance.now() + this.#resolve('work').approval.profile.requestTimeoutMs + 100;
    while (this.#activeHttp && performance.now() < deadline) await delay(2);
    if (this.#activeHttp) throw new IntegrationPolicyError('Pause drain incomplete');
  }
  resume() { this.#paused = false; }
  telemetry() {
    if (!this.#blueWindow || performance.now() - this.#blueWindow.at > 500) throw new IntegrationPolicyError('Availability window stale');
    return structuredClone(this.#blueWindow);
  }
}
