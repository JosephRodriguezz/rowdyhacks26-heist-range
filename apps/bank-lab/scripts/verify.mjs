import assert from 'node:assert/strict';

const base = new URL(process.argv[2] || 'http://bank:3000');
if (!['http:', 'https:'].includes(base.protocol) || base.pathname !== '/') {
  console.error('Use the bank origin without a path.'); process.exit(1);
}
async function request(path, {method = 'GET', cookie, data} = {}) {
  const response = await fetch(new URL(path, base), {method, redirect: 'error',
    signal: AbortSignal.timeout(10000), headers: {
      ...(cookie ? {cookie} : {}), ...(data ? {'content-type': 'application/json'} : {}),
      ...(method === 'POST' ? {origin: base.origin} : {}),
    }, ...(data ? {body: JSON.stringify(data)} : {})});
  const body = await response.json();
  return {status: response.status, body, cookie: response.headers.get('set-cookie')?.split(';')[0]};
}
try {
  const health = await request('/api/health');
  assert.equal(health.status, 200); assert.equal(health.body.status, 'ready');
  assert.equal((await request('/api/vault')).status, 401);
  const customer = await request('/api/login', {method: 'POST', data: {
    username: 'customer', password: process.env.BANK_CUSTOMER_PASSWORD}});
  assert.equal(customer.status, 200); assert.ok(customer.cookie);
  const accounts = await request('/api/accounts', {cookie: customer.cookie});
  assert.equal(accounts.status, 200); assert.equal(accounts.body.accounts.length, 2);
  assert.equal((await request('/api/accounts/2001', {cookie: customer.cookie})).status, 403);
  assert.equal((await request('/api/vault', {cookie: customer.cookie})).status, 403);
  const custodian = await request('/api/login', {method: 'POST', data: {
    username: 'vault', password: process.env.BANK_VAULT_PASSWORD}});
  assert.equal(custodian.status, 200); assert.ok(custodian.cookie);
  const vault = await request('/api/vault', {cookie: custodian.cookie});
  assert.equal(vault.status, 200);
  assert.ok(vault.body.records[0].synthetic_record.startsWith('LAB-ONLY-'));
  for (const cookie of [customer.cookie, custodian.cookie]) {
    assert.equal((await request('/api/logout', {method: 'POST', cookie})).status, 200);
    assert.equal((await request('/api/me', {cookie})).status, 401);
  }
  console.log('PASS: healthy lab, authorized accounts, cross-account denial, vault authorization, logout invalidation.');
  console.log('This verifies the bank baseline; it is not a contest referee verdict.');
} catch {
  console.error('FAIL: bank baseline check. Ensure the bank is running and reset has completed. No credentials or response bodies printed.');
  process.exitCode = 1;
}
