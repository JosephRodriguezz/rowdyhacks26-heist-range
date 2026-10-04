import {request} from 'node:http';
import {HARD_LIMITS} from './registry.mjs';

// No redirects, proxy, retries, user-selected paths, or unbounded response bodies.
export function boundedRequest({origin, path, method, headers, body, timeoutMs, signal}) {
  return new Promise(resolve => {
    if (signal?.aborted) return resolve({error: 'cancelled', status: 0, body: null});
    let settled = false;
    const controller = new AbortController();
    const cancel = () => controller.abort();
    const finish = result => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener('abort', cancel);
      resolve(result);
    };
    signal?.addEventListener('abort', cancel, {once: true});
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const req = request(new URL(path, origin), {method, headers, agent: false, signal: controller.signal}, response => {
      if (response.statusCode >= 300 && response.statusCode < 400) {
        finish({error: 'redirect_rejected', status: response.statusCode, body: null});
        response.destroy();
        return;
      }
      let bytes = 0;
      const chunks = [];
      response.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > HARD_LIMITS.responseBytes) {
          finish({error: 'response_too_large', status: response.statusCode, body: null});
          response.destroy();
          return;
        }
        chunks.push(chunk);
      });
      response.on('error', () => finish({error: signal?.aborted ? 'cancelled' : 'transport_error', status: 0, body: null}));
      response.on('end', () => {
        try {
          finish({status: response.statusCode, body: JSON.parse(Buffer.concat(chunks).toString('utf8'))});
        } catch {
          finish({error: 'invalid_response', status: response.statusCode, body: null});
        }
      });
    });
    req.on('error', () => finish({error: signal?.aborted ? 'cancelled' :
      controller.signal.aborted ? 'timeout' : 'transport_error', status: 0, body: null}));
    if (body !== undefined) req.write(JSON.stringify(body));
    req.end();
  });
}
