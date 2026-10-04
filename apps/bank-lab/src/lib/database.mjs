import pg from 'pg';
import {searchTrainingRecords as runTrainingSearch} from './training-search.mjs';

const connectionString = process.env.DATABASE_URL;
const pool = new pg.Pool({connectionString, max: 4, connectionTimeoutMillis: 3000,
  idleTimeoutMillis: 10000, statement_timeout: 5000});
// Log only a stable category; database errors can contain credentials and SQL.
pool.on('error', () => console.error('bank.database.unavailable'));

const trainingConnectionString = process.env.TRAINING_DATABASE_URL;
const trainingPool = new pg.Pool({connectionString: trainingConnectionString, max: 1,
  connectionTimeoutMillis: 2000, idleTimeoutMillis: 5000, statement_timeout: 1000});
trainingPool.on('error', () => console.error('bank.training_database.unavailable'));

export async function searchTrainingRecords(term) {
  if (!trainingConnectionString) throw new Error('Training database not configured');
  const client = await trainingPool.connect();
  try {
    await client.query('BEGIN READ ONLY');
    const records = await runTrainingSearch(client, term);
    await client.query('COMMIT');
    return records;
  } catch (error) {
    await client.query('ROLLBACK').catch(() => {});
    throw error;
  } finally { client.release(); }
}

/**
 * @template T
 * @param {(db: {query: (text: string, values?: unknown[]) => Promise<{rows: any[]}>}) => Promise<T>} callback
 * @returns {Promise<T>}
 */
export async function transaction(callback) {
  if (!connectionString) throw new Error('Database not configured');
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    // The private reset obtains the same lock: requests cannot see partial seeds.
    await client.query('SELECT pg_advisory_xact_lock(260026)');
    const result = await callback(client);
    await client.query('COMMIT');
    return result;
  } catch (error) {
    await client.query('ROLLBACK').catch(() => {});
    throw error;
  } finally { client.release(); }
}
