import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readHttpRequests, recordHttpRequest, resetHttpRequestsForTests} from '../src/lib/live-logs.mjs';

test('live request log retains bounded, sanitized application metadata', () => {
  resetHttpRequestsForTests();
  recordHttpRequest({method: 'POST', route: 'login', status: 401, durationMs: 12.6});
  recordHttpRequest({method: 'GET', route: 'accounts/1001', status: 200, durationMs: 5});
  const first = readHttpRequests(0);
  assert.equal(first.events.length, 2);
  assert.equal(first.events[0].route, '/api/login');
  assert.equal(first.events[1].route, '/api/accounts/:accountId');
  assert.equal(first.events[0].durationMs, 13);
  assert.ok(first.events.every(event => !('body' in event) && !('query' in event) && !('address' in event)));
  assert.equal(readHttpRequests(1).events.length, 1);
});

test('live request buffer drops old rows after its fixed capacity', () => {
  resetHttpRequestsForTests();
  for (let i = 0; i < 260; i++) recordHttpRequest({method: 'GET', route: 'health', status: 200, durationMs: 1});
  const page = readHttpRequests(0, 100);
  assert.equal(page.latest, 260);
  assert.equal(page.events.length, 100);
  assert.equal(page.events[0].sequence, 161);
  assert.equal(page.events.at(-1).sequence, 260);
  resetHttpRequestsForTests();
});
