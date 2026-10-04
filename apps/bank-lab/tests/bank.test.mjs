import {test, before, beforeEach, after} from 'node:test';
import assert from 'node:assert/strict';
import {randomBytes} from 'node:crypto';
import {PGlite} from '@electric-sql/pglite';
import {login, logout, read, resetDatabase, state} from '../src/lib/bank.mjs';
import {provisionAppRole, validateDatabasePasswords} from '../src/lib/setup.mjs';
import {provisionTrainingRole} from '../src/lib/setup.mjs';
import {searchTrainingRecords, trainingSearchSql} from '../src/lib/training-search.mjs';

let db;
let engine;
const config = {customerPassword: randomBytes(24).toString('hex'), vaultPassword: randomBytes(24).toString('hex')};
before(async () => {
  engine = new PGlite(); await engine.waitReady;
  // Match pg's simple-query protocol for parameterless multi-statement DDL.
  db = {query: async (text, values) => values
    ? engine.query(text, values) : (await engine.exec(text)).at(-1)};
});
beforeEach(async () => {await db.query('RESET ROLE'); await resetDatabase(db, config);});
after(async () => {await engine.close();});

test('baseline separates normal account access from protected records', async () => {
  assert.equal((await read(db, 'vault', null)).status, 401);
  const customer = await login(db, 'customer', config.customerPassword);
  assert.equal(customer.status, 200);
  const accounts = await read(db, 'accounts', customer.token);
  assert.deepEqual(accounts.body.accounts.map(a => a.account_id), ['1001', '1002']);
  assert.equal((await read(db, 'accounts', customer.token, '2001')).status, 403);
  assert.equal((await read(db, 'vault', customer.token)).status, 403);
  const custodian = await login(db, 'vault', config.vaultPassword);
  const records = await read(db, 'vault', custodian.token);
  assert.equal(records.status, 200);
  assert.equal(records.body.records.length, 1);
});

test('credential rejection and parameterized queries do not bypass login', async () => {
  assert.equal((await login(db, 'customer', 'wrong-password')).status, 401);
  assert.equal((await login(db, "' OR TRUE --", config.customerPassword)).status, 401);
  assert.equal((await login(db, {}, config.customerPassword)).status, 401);
  assert.equal((await login(db, 'customer', 'x'.repeat(257))).status, 401);
});

test('session values are hashed, expire, and are invalidated on logout', async () => {
  const session = await login(db, 'customer', config.customerPassword);
  const stored = (await db.query('SELECT token_hash FROM bank.sessions')).rows[0].token_hash;
  assert.notEqual(stored, session.token);
  assert.equal((await read(db, 'me', session.token)).status, 200);
  await db.query("UPDATE bank.sessions SET expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second'");
  assert.equal((await read(db, 'me', session.token)).status, 401);
  const again = await login(db, 'customer', config.customerPassword);
  await logout(db, again.token);
  assert.equal((await read(db, 'me', again.token)).status, 401);
});

test('reset rotates the run, restores accounts, and revokes prior sessions', async () => {
  const old = await state(db);
  const session = await login(db, 'customer', config.customerPassword);
  await db.query("UPDATE bank.accounts SET balance_cents = 0 WHERE account_id = '1001'");
  const run = await resetDatabase(db, config);
  assert.notEqual(run, old.run_id);
  assert.equal((await read(db, 'me', session.token)).status, 401);
  assert.equal((await db.query("SELECT balance_cents FROM bank.accounts WHERE account_id = '1001'")).rows[0].balance_cents, 245080);
  assert.equal((await db.query('SELECT COUNT(*)::int AS count FROM bank.events')).rows[0].count, 0);
});

test('failed reset configuration preserves the existing baseline', async () => {
  const old = await state(db);
  await assert.rejects(resetDatabase(db, {customerPassword: 'short', vaultPassword: 'short'}));
  assert.equal((await state(db)).run_id, old.run_id);
});

test('operator rejects shared administrator, web, and training database credentials', () => {
  const admin = randomBytes(32).toString('hex');
  const app = randomBytes(32).toString('hex');
  const training = randomBytes(32).toString('hex');
  const url = `postgresql://lab_admin:${admin}@db:5432/bank_lab`;
  assert.doesNotThrow(() => validateDatabasePasswords(url, app, training));
  assert.throws(() => validateDatabasePasswords(url, admin, training));
  assert.throws(() => validateDatabasePasswords(url, app, app));
  assert.throws(() => validateDatabasePasswords(url, app, 'replace_with_password'));
});

test('training search demonstrates injection only against read-only synthetic records', async () => {
  const trainingPassword = randomBytes(32).toString('hex');
  await provisionTrainingRole(db, trainingPassword);
  await db.query('SET ROLE bank_training');
  await db.query('BEGIN READ ONLY');
  const ordinary = await searchTrainingRecords(db, 'identity');
  assert.deepEqual(ordinary.map(row => row.record_id), ['guide-2']);
  const injected = await searchTrainingRecords(db, "' OR TRUE --");
  assert.deepEqual(injected.map(row => row.record_id).sort(), ['guide-1', 'guide-2', 'guide-3']);
  await db.query('SAVEPOINT denied_cross_table_read');
  await assert.rejects(db.query('SELECT username FROM bank.users'), /permission denied/);
  await db.query('ROLLBACK TO SAVEPOINT denied_cross_table_read');
  await db.query('SAVEPOINT denied_fixture_write');
  await assert.rejects(db.query("UPDATE bank.training_records SET label = 'changed'"), /read-only transaction/);
  await db.query('ROLLBACK TO SAVEPOINT denied_fixture_write');
  await db.query('ROLLBACK');
  await db.query('RESET ROLE');
  assert.match(trainingSearchSql('identity'), /ILIKE '%identity%'/);
  assert.throws(() => trainingSearchSql('x'.repeat(65)), RangeError);
});

test('telemetry contains safe categories instead of credentials or vault contents', async () => {
  const session = await login(db, 'vault', config.vaultPassword);
  const vault = await read(db, 'vault', session.token);
  const events = (await db.query('SELECT * FROM bank.events ORDER BY sequence')).rows;
  assert.deepEqual(events.map(e => e.event_type), ['auth.login_succeeded', 'vault.authorized_access']);
  const serialized = JSON.stringify(events);
  assert.ok(!serialized.includes(config.vaultPassword));
  assert.ok(!serialized.includes(session.token));
  assert.ok(!serialized.includes(vault.body.records[0].synthetic_record));
  assert.ok(events.every(e => e.visibility === 'blue_private'));
  assert.ok(events.every(e => e.producer === 'lab' && e.source_mode === 'live'));
});

test('web database role cannot reset, mutate balances, or read the operator event store', async () => {
  await provisionAppRole(db, randomBytes(32).toString('hex'));
  await db.query('SET ROLE bank_app');
  const session = await login(db, 'customer', config.customerPassword);
  assert.equal((await read(db, 'accounts', session.token)).status, 200);
  await assert.rejects(db.query('TRUNCATE bank.users CASCADE'), /permission denied/);
  await assert.rejects(db.query('UPDATE bank.accounts SET balance_cents = 0'), /permission denied/);
  await assert.rejects(db.query('SELECT * FROM bank.events'), /permission denied/);
  await assert.rejects(db.query('SELECT * FROM bank.training_records'), /permission denied/);
});
