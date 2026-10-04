/**
 * Intentionally unsafe query builder for the opt-in SQL injection exercise.
 * Production use must stay behind the dedicated, read-only bank_training role.
 */
export function trainingSearchSql(term) {
  if (typeof term !== 'string' || term.length > 64) throw new RangeError('Search term must be 64 characters or fewer');
  return `SELECT record_id, label FROM bank.training_records WHERE label ILIKE '%${term}%' LIMIT 20`;
}

export async function searchTrainingRecords(db, term) {
  return (await db.query(trainingSearchSql(term))).rows;
}
