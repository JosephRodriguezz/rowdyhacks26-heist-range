import pg from 'pg';
import {resetDatabase} from '../src/lib/bank.mjs';
import {provisionAppRole, provisionTrainingRole, validateDatabasePasswords} from '../src/lib/setup.mjs';

const adminUrl = process.env.DATABASE_ADMIN_URL;
if (!adminUrl) { console.error('Reset requires the private operator service.'); process.exit(1); }
const client = new pg.Client({connectionString: adminUrl, connectionTimeoutMillis: 5000});
let transactionOpen = false;
try {
  validateDatabasePasswords(adminUrl, process.env.BANK_APP_DB_PASSWORD, process.env.BANK_TRAINING_DB_PASSWORD);
  await client.connect();
  await client.query('BEGIN');
  transactionOpen = true;
  await client.query('SELECT pg_advisory_xact_lock(260026)');
  const runId = await resetDatabase(client, {
    customerPassword: process.env.BANK_CUSTOMER_PASSWORD,
    vaultPassword: process.env.BANK_VAULT_PASSWORD,
    scenarioVersion: process.env.BANK_SCENARIO === 'sqli-training' ? 'training-v1' : 'baseline-v1',
  });
  await provisionAppRole(client, process.env.BANK_APP_DB_PASSWORD);
  await provisionTrainingRole(client, process.env.BANK_TRAINING_DB_PASSWORD);
  await client.query('COMMIT');
  transactionOpen = false;
  console.log(`Baseline ready. Run ID: ${runId}. Previous sessions invalidated.`);
} catch {
  if (transactionOpen) await client.query('ROLLBACK').catch(() => {});
  console.error('Reset failed. Check database readiness and seed/password requirements in the guide.');
  process.exitCode = 1;
} finally { await client.end().catch(() => {}); }
