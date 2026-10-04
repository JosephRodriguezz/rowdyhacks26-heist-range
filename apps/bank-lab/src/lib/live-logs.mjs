const MAX_LOGS = 250;
const entries = [];
let sequence = 0;

function normalizeRoute(route) {
  if (route === 'health' || route === 'login' || route === 'logout' || route === 'me' ||
      route === 'accounts' || route === 'vault' || route === 'training/search') return `/api/${route}`;
  if (route.startsWith('accounts/')) return '/api/accounts/:accountId';
  return '/api/other';
}

export function recordHttpRequest({method, route, status, durationMs}) {
  const entry = {
    sequence: ++sequence,
    timestamp: new Date().toISOString(),
    method: method === 'POST' ? 'POST' : 'GET',
    route: normalizeRoute(route),
    status: Number.isInteger(status) && status >= 100 && status <= 599 ? status : 500,
    durationMs: Number.isFinite(durationMs) ? Math.max(0, Math.round(durationMs)) : 0,
  };
  entries.push(entry);
  if (entries.length > MAX_LOGS) entries.splice(0, entries.length - MAX_LOGS);
  return entry;
}

export function readHttpRequests(after = 0, limit = 100) {
  const cursor = Number.isSafeInteger(after) && after >= 0 ? after : 0;
  const pageSize = Number.isInteger(limit) ? Math.max(1, Math.min(limit, 100)) : 100;
  return {
    events: entries.filter(entry => entry.sequence > cursor).slice(-pageSize),
    latest: sequence,
  };
}

export function resetHttpRequestsForTests() {
  entries.length = 0;
  sequence = 0;
}
