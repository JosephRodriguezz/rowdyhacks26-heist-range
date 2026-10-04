export function allowedOrigin(origin, configured = process.env.BANK_ALLOWED_ORIGINS || 'http://localhost:3000') {
  return typeof origin === 'string' && configured.split(',').map(value => value.trim()).includes(origin);
}
export async function boundedJson(request, limit = 4096) {
  const reader = request.body?.getReader();
  if (!reader) throw new Error('JSON required');
  let length = 0;
  const chunks = [];
  try {
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > limit) {await reader.cancel(); throw new RangeError('Request too large');}
      chunks.push(value);
    }
  } finally {reader.releaseLock();}
  const all = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {all.set(chunk, offset); offset += chunk.byteLength;}
  const input = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(all));
  if (!input || Array.isArray(input) || typeof input !== 'object') throw new Error('JSON object required');
  return input;
}
