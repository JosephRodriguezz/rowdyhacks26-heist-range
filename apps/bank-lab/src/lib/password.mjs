import {randomBytes, scrypt, timingSafeEqual, createHash} from 'node:crypto';
import {promisify} from 'node:util';

const derive = promisify(scrypt);
export async function hashPassword(password) {
  const salt = randomBytes(16).toString('hex');
  const key = await derive(password, salt, 64);
  return `scrypt:${salt}:${key.toString('hex')}`;
}
export async function checkPassword(password, stored) {
  const [kind, salt, hex] = stored.split(':');
  if (kind !== 'scrypt' || !salt || !/^[a-f0-9]{128}$/.test(hex ?? '')) return false;
  const key = await derive(password, salt, 64);
  return timingSafeEqual(key, Buffer.from(hex, 'hex'));
}
export function hashToken(token) {
  return createHash('sha256').update(token).digest('hex');
}
