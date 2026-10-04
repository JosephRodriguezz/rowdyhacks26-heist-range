import {randomBytes, randomUUID} from 'node:crypto';
import {hashToken, hashPassword, checkPassword} from './password.mjs';

const SESSION_SECONDS = 1800;
export const targetId = process.env.BANK_TARGET_ID || 'bank-lab';

export async function state(db) {
  const result = await db.query('SELECT run_id, scenario_version FROM bank.state WHERE singleton = TRUE');
  if (!result.rows[0]) throw new Error('Lab requires reset');
  return result.rows[0];
}
async function event(db, current, type, actor = 'anonymous') {
  const id = randomUUID();
  await db.query(`INSERT INTO bank.events
    (event_id, run_id, target_id, event_type, actor_id, visibility, summary)
    VALUES ($1, $2, $3, $4, $5, 'blue_private', $6)`,
  [id, current.run_id, targetId, type, actor, type.replaceAll('.', ' ')]);
  return id;
}
async function authenticate(db, token, current) {
  if (typeof token !== 'string' || !/^[a-f0-9]{64}$/.test(token)) return null;
  const result = await db.query(`SELECT u.user_id, u.username, u.display_name, u.role
    FROM bank.sessions s JOIN bank.users u ON s.user_id = u.user_id
    WHERE s.token_hash = $1 AND s.run_id = $2 AND s.expires_at > CURRENT_TIMESTAMP`,
  [hashToken(token), current.run_id]);
  return result.rows[0] || null;
}
export async function login(db, username, password) {
  const current = await state(db);
  if (typeof username !== 'string' || typeof password !== 'string' ||
      username.length > 64 || password.length > 256 || !password) {
    await event(db, current, 'auth.login_failed');
    return {status: 401, body: {error: 'Invalid username or password'}};
  }
  const lookup = await db.query('SELECT * FROM bank.users WHERE username = $1', [username]);
  const user = lookup.rows[0];
  // Also perform password work for unknown names; do not reveal account existence.
  const dummy = 'scrypt:00000000000000000000000000000000:' + '00'.repeat(64);
  const valid = await checkPassword(password, user?.password_hash || dummy);
  if (!user || !valid) {
    await event(db, current, 'auth.login_failed');
    return {status: 401, body: {error: 'Invalid username or password'}};
  }
  const token = randomBytes(32).toString('hex');
  await db.query(`INSERT INTO bank.sessions (token_hash, run_id, user_id, expires_at)
    VALUES ($1, $2, $3, CURRENT_TIMESTAMP + INTERVAL '30 minutes')`,
  [hashToken(token), current.run_id, user.user_id]);
  await event(db, current, 'auth.login_succeeded', user.user_id);
  return {status: 200, body: {message: 'Signed in'}, token, maxAge: SESSION_SECONDS};
}
export async function logout(db, token) {
  const current = await state(db);
  const user = await authenticate(db, token, current);
  if (user) {
    await db.query('DELETE FROM bank.sessions WHERE token_hash = $1', [hashToken(token)]);
    await event(db, current, 'auth.logout', user.user_id);
  }
  return {status: 200, body: {message: 'Signed out'}};
}
export async function read(db, resource, token, accountId) {
  const current = await state(db);
  const user = await authenticate(db, token, current);
  if (!user) {
    if (resource === 'vault') await event(db, current, 'vault.access_denied');
    return {status: 401, body: {error: 'Sign in to continue'}};
  }
  if (resource === 'me') return {status: 200, body: {user, run_id: current.run_id}};
  if (resource === 'accounts') {
    if (accountId && !/^\d{4}$/.test(accountId)) return {status: 400, body: {error: 'Invalid account identifier'}};
    const result = accountId
      ? await db.query('SELECT * FROM bank.accounts WHERE account_id = $1 AND owner_id = $2', [accountId, user.user_id])
      : await db.query('SELECT * FROM bank.accounts WHERE owner_id = $1 ORDER BY account_id', [user.user_id]);
    if (accountId && result.rows.length === 0) {
      await event(db, current, 'account.access_denied', user.user_id);
      return {status: 403, body: {error: 'Account unavailable'}};
    }
    await event(db, current, 'account.viewed', user.user_id);
    return {status: 200, body: {accounts: result.rows, run_id: current.run_id}};
  }
  if (resource === 'vault') {
    if (user.role !== 'vault') {
      await event(db, current, 'vault.access_denied', user.user_id);
      return {status: 403, body: {error: 'Vault authorization required'}};
    }
    const result = await db.query('SELECT vault_id, label, synthetic_record FROM bank.vault');
    await event(db, current, 'vault.authorized_access', user.user_id);
    return {status: 200, body: {records: result.rows, run_id: current.run_id}};
  }
  return {status: 404, body: {error: 'Route not found'}};
}

export async function resetDatabase(db, config) {
  const {customerPassword, vaultPassword, scenarioVersion = 'baseline-v1'} = config;
  if (typeof customerPassword !== 'string' || typeof vaultPassword !== 'string' ||
      customerPassword.length < 16 || vaultPassword.length < 16 ||
      customerPassword.length > 256 || vaultPassword.length > 256 ||
      customerPassword === vaultPassword || customerPassword.startsWith('replace_') || vaultPassword.startsWith('replace_')) {
    throw new Error('Set different non-placeholder seed passwords of 16 to 256 characters');
  }
  await db.query(`CREATE SCHEMA IF NOT EXISTS bank;
    CREATE TABLE IF NOT EXISTS bank.state (
      singleton boolean PRIMARY KEY CHECK(singleton), run_id uuid NOT NULL, scenario_version text NOT NULL);
    CREATE TABLE IF NOT EXISTS bank.users (
      user_id text PRIMARY KEY, username text UNIQUE NOT NULL, display_name text NOT NULL,
      role text NOT NULL CHECK(role IN ('customer', 'vault')), password_hash text NOT NULL);
    CREATE TABLE IF NOT EXISTS bank.accounts (
      account_id text PRIMARY KEY, owner_id text NOT NULL REFERENCES bank.users(user_id),
      label text NOT NULL, balance_cents integer NOT NULL CHECK(balance_cents >= 0));
    CREATE TABLE IF NOT EXISTS bank.sessions (
      token_hash text PRIMARY KEY, run_id uuid NOT NULL, user_id text NOT NULL REFERENCES bank.users(user_id),
      expires_at timestamptz NOT NULL);
    CREATE TABLE IF NOT EXISTS bank.vault (
      vault_id text PRIMARY KEY, label text NOT NULL, synthetic_record text NOT NULL);
    CREATE TABLE IF NOT EXISTS bank.training_records (
      record_id text PRIMARY KEY, label text NOT NULL);
    CREATE TABLE IF NOT EXISTS bank.events (
      sequence bigserial PRIMARY KEY, event_id uuid UNIQUE NOT NULL, run_id uuid NOT NULL,
      occurred_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP, target_id text NOT NULL,
      event_type text NOT NULL, actor_id text NOT NULL, visibility text NOT NULL, summary text NOT NULL,
      producer text NOT NULL DEFAULT 'lab' CHECK(producer = 'lab'),
      source_mode text NOT NULL DEFAULT 'live' CHECK(source_mode = 'live'));
    TRUNCATE bank.sessions, bank.accounts, bank.users, bank.vault, bank.training_records, bank.events, bank.state RESTART IDENTITY;`);
  const runId = randomUUID();
  await db.query('INSERT INTO bank.state VALUES (TRUE, $1, $2)', [runId, scenarioVersion]);
  for (const [id, username, name, role, password] of [
    ['user-customer', 'customer', 'Lab Customer', 'customer', customerPassword],
    ['user-vault', 'vault', 'Vault Custodian', 'vault', vaultPassword],
  ]) {
    await db.query('INSERT INTO bank.users VALUES ($1, $2, $3, $4, $5)',
      [id, username, name, role, await hashPassword(password)]);
  }
  await db.query(`INSERT INTO bank.accounts VALUES
    ('1001', 'user-customer', 'Everyday account', 245080),
    ('1002', 'user-customer', 'Reserve account', 1250000),
    ('2001', 'user-vault', 'Custodian account', 800000)`);
  await db.query('INSERT INTO bank.vault VALUES ($1, $2, $3)',
    ['vault-main', 'Synthetic vault ledger', `LAB-ONLY-${randomBytes(16).toString('hex')}`]);
  await db.query(`INSERT INTO bank.training_records VALUES
    ('guide-1', 'Training guide: recognize unusual account activity'),
    ('guide-2', 'Training guide: verify a customer identity'),
    ('guide-3', 'Training guide: report a suspicious transfer')`);
  return runId;
}
