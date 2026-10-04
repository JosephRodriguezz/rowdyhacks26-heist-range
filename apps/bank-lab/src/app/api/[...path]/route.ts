import {NextRequest, NextResponse} from 'next/server';
import {transaction, searchTrainingRecords} from '../../../lib/database.mjs';
import {state, targetId, login, logout, read} from '../../../lib/bank.mjs';
import {readHttpRequests, recordHttpRequest} from '../../../lib/live-logs.mjs';
import {allowedOrigin, boundedJson} from '../../../lib/request-policy.mjs';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
const COOKIE = 'bank_session';
const headers = {'Cache-Control': 'no-store'};
type Context = {params: Promise<{path: string[]}>};
type ActionResult = {status: number; body: Record<string, unknown>; token?: string; maxAge?: number};

async function handleGet(request: NextRequest, context: Context) {
  const {path} = await context.params;
  const route = path.join('/');
  if (route === 'health') {
    try {
      const current = await transaction(state);
      return NextResponse.json({status: 'ready', target_id: targetId, ...current}, {headers});
    } catch {
      return NextResponse.json({status: 'unavailable', target_id: targetId}, {status: 503, headers});
    }
  }
  if (route === 'monitor/logs') {
    const afterValue = request.nextUrl.searchParams.get('after') ?? '0';
    const after = /^\d{1,16}$/.test(afterValue) ? Number(afterValue) : 0;
    return NextResponse.json(readHttpRequests(after), {headers});
  }
  if (route === 'training/search') {
    if (process.env.BANK_SCENARIO !== 'sqli-training') {
      return NextResponse.json({error: 'Route not found'}, {status: 404, headers});
    }
    const term = request.nextUrl.searchParams.get('term') ?? '';
    if (term.length > 64) return NextResponse.json({error: 'Search term too long'}, {status: 400, headers});
    try {
      const records = await searchTrainingRecords(term);
      return NextResponse.json({records}, {headers});
    } catch {
      return NextResponse.json({error: 'Training search temporarily unavailable'}, {status: 503, headers});
    }
  }
  const allowed = ['me', 'accounts', 'vault'].includes(route) ||
    (path.length === 2 && path[0] === 'accounts');
  if (!allowed) return NextResponse.json({error: 'Route not found'}, {status: 404, headers});
  try {
    const result = await transaction(db => read(db, path[0], request.cookies.get(COOKIE)?.value, path[1]));
    return NextResponse.json(result.body, {status: result.status, headers});
  } catch {
    return NextResponse.json({error: 'Bank temporarily unavailable'}, {status: 503, headers});
  }
}

export async function GET(request: NextRequest, context: Context) {
  const started = performance.now();
  const {path} = await context.params;
  const route = path.join('/');
  let status = 500;
  try {
    const response = await handleGet(request, context);
    status = response.status;
    return response;
  } finally {
    if (route !== 'monitor/logs') {
      recordHttpRequest({method: 'GET', route, status, durationMs: performance.now() - started});
    }
  }
}

async function handlePost(request: NextRequest, context: Context) {
  const {path} = await context.params;
  if (path.length !== 1 || !['login', 'logout'].includes(path[0])) {
    return NextResponse.json({error: 'Route not found'}, {status: 404, headers});
  }
  if (!allowedOrigin(request.headers.get('origin'))) {
    return NextResponse.json({error: 'Request origin rejected'}, {status: 403, headers});
  }
  let input: {username?: unknown; password?: unknown} = {};
  if (path[0] === 'login') {
    if (!request.headers.get('content-type')?.toLowerCase().startsWith('application/json')) {
      return NextResponse.json({error: 'JSON required'}, {status: 415, headers});
    }
    try {
      input = await boundedJson(request);
    } catch (error) {
      if (error instanceof RangeError) return NextResponse.json({error: 'Request too large'}, {status: 413, headers});
      return NextResponse.json({error: 'Invalid JSON'}, {status: 400, headers});
    }
  }
  try {
    const result = await transaction<ActionResult>(db => path[0] === 'login'
      ? login(db, input.username, input.password)
      : logout(db, request.cookies.get(COOKIE)?.value));
    const response = NextResponse.json(result.body, {status: result.status, headers});
    if ('token' in result && result.token) {
      response.cookies.set(COOKIE, result.token, {httpOnly: true, sameSite: 'strict',
        secure: process.env.BANK_COOKIE_SECURE !== '0', maxAge: result.maxAge, path: '/'});
    } else if (path[0] === 'logout') {
      response.cookies.set(COOKIE, '', {httpOnly: true, sameSite: 'strict',
        secure: process.env.BANK_COOKIE_SECURE !== '0', maxAge: 0, path: '/'});
    }
    return response;
  } catch {
    return NextResponse.json({error: 'Bank temporarily unavailable'}, {status: 503, headers});
  }
}

export async function POST(request: NextRequest, context: Context) {
  const started = performance.now();
  const {path} = await context.params;
  const route = path.join('/');
  let status = 500;
  try {
    const response = await handlePost(request, context);
    status = response.status;
    return response;
  } finally {
    recordHttpRequest({method: 'POST', route, status, durationMs: performance.now() - started});
  }
}
