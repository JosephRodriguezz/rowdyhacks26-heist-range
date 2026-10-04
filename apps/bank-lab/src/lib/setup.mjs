export function validateDatabasePasswords(adminUrl, appPassword, trainingPassword) {
  const adminPassword = new URL(adminUrl).password;
  if (!/^[a-f0-9]{32,}$/.test(adminPassword) || !/^[a-f0-9]{32,}$/.test(appPassword || '') ||
      !/^[a-f0-9]{32,}$/.test(trainingPassword || '') ||
      new Set([adminPassword, appPassword, trainingPassword]).size !== 3) {
    throw new Error('Use three different database passwords with 32+ hexadecimal characters');
  }
}

export async function provisionTrainingRole(db, password) {
  if (!/^[a-f0-9]{32,}$/.test(password || '')) throw new Error('Training DB password must be 32+ hex characters');
  // This fixed role can read only the synthetic fixture table for the opt-in demo.
  await db.query(`DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bank_training') THEN
      CREATE ROLE bank_training LOGIN PASSWORD '${password}';
    ELSE ALTER ROLE bank_training PASSWORD '${password}'; END IF;
  END $$;
  REVOKE ALL ON SCHEMA bank FROM PUBLIC, bank_training;
  GRANT USAGE ON SCHEMA bank TO bank_training;
  REVOKE ALL ON ALL TABLES IN SCHEMA bank FROM bank_training;
  REVOKE ALL ON ALL SEQUENCES IN SCHEMA bank FROM bank_training;
  GRANT SELECT ON bank.training_records TO bank_training;`);
}

export async function provisionAppRole(db, password) {
  if (!/^[a-f0-9]{32,}$/.test(password || '')) throw new Error('Application DB password must be 32+ hex characters');
  // Identifier is fixed; password is validated hex before this DDL is composed.
  await db.query(`DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bank_app') THEN
      CREATE ROLE bank_app LOGIN PASSWORD '${password}';
    ELSE ALTER ROLE bank_app PASSWORD '${password}'; END IF;
  END $$;
  REVOKE ALL ON SCHEMA bank FROM PUBLIC;
  GRANT USAGE ON SCHEMA bank TO bank_app;
  GRANT SELECT ON bank.state, bank.users, bank.accounts, bank.vault, bank.sessions TO bank_app;
  GRANT INSERT, DELETE ON bank.sessions TO bank_app;
  GRANT INSERT ON bank.events TO bank_app;
  GRANT USAGE, SELECT ON SEQUENCE bank.events_sequence_seq TO bank_app;`);
}
