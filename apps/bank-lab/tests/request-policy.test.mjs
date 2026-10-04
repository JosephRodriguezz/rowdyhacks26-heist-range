import {test} from 'node:test';
import assert from 'node:assert/strict';
import {allowedOrigin, boundedJson} from '../src/lib/request-policy.mjs';

test('fixed origin allowlist supports SSH and internal verification while rejecting unrelated origins', () => {
  const list = 'http://localhost:3000,http://bank:3000';
  assert.ok(allowedOrigin('http://localhost:3000', list));
  assert.ok(allowedOrigin('http://bank:3000', list));
  assert.ok(!allowedOrigin('http://localhost:3000.attacker.invalid', list));
  assert.ok(!allowedOrigin('http://attacker.invalid', list));
  assert.ok(!allowedOrigin(null, list));
  assert.ok(!allowedOrigin('null', list));
});
test('JSON parser bounds actual bytes and rejects malformed or non-object bodies', async () => {
  const request = text => new Request('http://localhost/api/login', {method: 'POST', body: text});
  assert.deepEqual(await boundedJson(request('{"username":"customer"}')), {username: 'customer'});
  await assert.rejects(boundedJson(request('x'.repeat(4097))), RangeError);
  await assert.rejects(boundedJson(request('[]')));
  await assert.rejects(boundedJson(request('null')));
  await assert.rejects(boundedJson(request('{broken')));
});
