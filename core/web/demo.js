'use strict';
// Only the existing authenticated judge projection is consumed here.
const $ = id => document.getElementById(id);
let session = null, events = [], cursor = 0, authenticated = false, busy = false, polling = false;
let presenterToken = null;
const terminal = new Set(['completed', 'cancelled', 'failed']);
const actionId = () => 'presenter-' + crypto.randomUUID();
const text = (id, value) => { $(id).textContent = value; };
function problem(message = '') { $('error').hidden = !message; text('error', message); }
async function api(path, body) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (presenterToken) headers.Authorization = 'Bearer ' + presenterToken;
  const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST', headers,
    body: body === undefined ? undefined : JSON.stringify(body), credentials: 'omit',
    cache: 'no-store', signal: AbortSignal.timeout(6000)});
  const value = await response.json();
  if (response.status === 401) { authenticated = false; presenterToken = null; sessionStorage.removeItem('rowdy-presenter'); $('login').hidden = false; }
  if (!response.ok) throw new Error(value.error?.message || 'The request did not complete.');
  return value;
}
function buttons() {
  const allowed = authenticated && session ? session.allowed_actions : [];
  $('start').disabled = busy || !authenticated || (session && !allowed.includes('start'));
  $('pause').disabled = busy || !allowed.some(a => a === 'pause' || a === 'resume');
  text('pause', allowed.includes('resume') ? 'Resume' : 'Pause');
  $('stop').disabled = busy || !allowed.includes('stop');
  $('reset').disabled = busy || !allowed.includes('reset');
  $('history').disabled = busy;
  $('export').disabled = !session || events.length === 0;
}
function eventTitle(e) {
  const d = e.data || {};
  switch (e.type) {
    case 'availability.request.observed': return `Load request · HTTP ${d.http_status ?? 'unavailable'} · ${d.refusal_reason === 'rate_limit' ? 'limited by policy' : d.status}`;
    case 'availability.probe.observed': return `${{health:'Readiness', ordinary:'Authorized accounts', status:'Training capacity'}[d.kind] || 'Probe'} · ${d.status}`;
    case 'target.health': return 'Healthy baseline verified';
    case 'availability.load.dispatched': return d.capability === 'start_load_test' ? 'Core dispatched bounded Red load' : 'Core stopped Red load';
    case 'availability.observed': return `Blue observed ${d.requests} requests · ${d.inflight} in flight`;
    case 'availability.defense.applied': return 'Blue limit applied · recovery still requires verification';
    case 'availability.referee.assessed': return d.summary;
    default: return e.type.replaceAll('.', ' ');
  }
}
function renderTimeline(incoming) {
  const log = $('timeline'), follow = log.scrollTop + log.clientHeight >= log.scrollHeight - 50;
  if (!events.length) log.replaceChildren();
  for (const e of incoming) {
    const row = document.createElement('div'); row.className = 'event';
    const time = document.createElement('time'); time.textContent = new Date(e.timestamp).toLocaleTimeString([], {hour12:false});
    const actor = document.createElement('span'); actor.className = 'actor'; actor.textContent = e.actor === 'core-bank-adapter' ? 'Bank probe' : e.actor;
    const detail = document.createElement('div'), title = document.createElement('strong'), sub = document.createElement('small');
    title.textContent = eventTitle(e);
    const d = e.data || {}, pieces = [`#${e.sequence}`, e.data_source];
    if (typeof d.latency_ms === 'number') pieces.push(`${d.latency_ms.toFixed(1)} ms`);
    if (typeof d.active === 'number') pieces.push(`${d.active} active`);
    if (d.error) pieces.push(d.error.replaceAll('_', ' '));
    sub.textContent = pieces.join(' · '); detail.append(title, sub); row.append(time, actor, detail); log.append(row);
  }
  while (log.children.length > 500) log.firstChild.remove();
  if (follow) log.scrollTop = log.scrollHeight;
}
function render() {
  buttons();
  text('connection', authenticated ? 'Connected to local core' : 'Presenter disconnected');
  if (!session) return;
  const seen = type => events.filter(e => e.type === type);
  const last = type => seen(type).at(-1)?.data;
  const probes = seen('availability.probe.observed'), status = probes.filter(e => e.data.kind === 'status').at(-1)?.data;
  const responses = seen('availability.request.observed');
  const ended = terminal.has(session.status), baseline = !!last('target.health'), defense = !!last('availability.defense.applied');
  const final = last('availability.referee.assessed');
  text('run-title', {created:'Ready for a fresh run',running:'Demo in progress',paused:'Demo paused',pausing:'Draining admitted requests',stopping:'Stopping safely',completed:'Run complete',cancelled:'Run stopped',failed:'Run ended — evidence incomplete'}[session.status] || session.status);
  text('run-detail', ended ? 'Evidence is saved. Choose New run for a fresh bank, or export this report.' : 'The original deadline stays in effect while paused. Stop cancels the run.');
  text('session-id', session.id);
  text('bank-state', status ? (status.status === 'available' ? 'Available' : status.status === 'degraded' ? 'Capacity degraded' : 'Inconclusive') : 'Awaiting baseline');
  text('bank-detail', status ? `Last measured training occupancy: ${status.active ?? 0}. ${ended ? 'Target has been torn down; this is the final observation.' : 'Ordinary accounts are checked separately.'}` : 'Readiness and authorized accounts are checked before load starts.');
  $('bank-meter').classList.toggle('measured', !!status);
  const started = seen('availability.load.dispatched').some(e => e.data.capability === 'start_load_test');
  text('red-state', ended && started ? 'Load stopped' : started ? 'Bounded load dispatched' : 'Standing by');
  text('request-count', responses.length);
  text('refused-count', responses.filter(e => e.data.refusal_reason === 'rate_limit').length);
  text('blue-state', defense ? 'Temporary limit applied' : last('availability.observed') ? 'Analyzing pressure' : 'Waiting for evidence');
  text('blue-detail', defense ? 'Only the registered load client is limited: 1 request/second, burst 1, 3-second expiry.' : 'The actual detector sees sanitized target telemetry, then proposes a narrow limit.');
  const verified = ended && final?.result === 'achieved' && session.verdict?.result === 'achieved';
  text('verdict', verified ? 'Recovery verified' : ended ? 'Inconclusive' : 'Not assessed');
  text('verdict-detail', verified ? 'Independent checks passed during continuing load; normal account access was preserved.' : ended ? 'This run does not establish recovery. Review the observations and start a fresh run.' : 'A defense receipt alone does not prove recovery.');
  const checks = $('checks'); checks.replaceChildren();
  for (const [ok, label] of [[baseline, 'Healthy baseline'], [defense, 'Source limit applied'], [verified, 'Recovery + ordinary access verified']]) {
    const line = document.createElement('span'); line.className = ok ? 'pass' : 'pending'; line.textContent = (ok ? '✓ ' : '○ ') + label; checks.append(line);
  }
}
async function refresh() {
  if (!session) return;
  const selected = session.id;
  const [snapshot, batch] = await Promise.all([api(`/api/assessments/${selected}`), api(`/api/assessments/${selected}/events?after=${cursor}`)]);
  if (session?.id !== selected) return;
  session = snapshot;
  const incoming = batch.events.filter(e => e.sequence > cursor);
  renderTimeline(incoming); events.push(...incoming); cursor = batch.last_event_id;
  render();
}
async function history() {
  const {assessments} = await api('/api/assessments');
  const rows = assessments.filter(s => s.target_id === 'availability-fixture');
  $('history').replaceChildren();
  for (const row of rows.slice(-30).reverse()) {
    const option = document.createElement('option'); option.value = row.id;
    option.textContent = `${row.id.slice(-6)} · ${row.status}`; option.selected = session?.id === row.id; $('history').append(option);
  }
  return rows;
}
async function select(snapshot) {
  session = snapshot; events = []; cursor = 0;
  $('report-preview').hidden = true; text('report-json', '');
  $('timeline').replaceChildren(); await refresh(); await history();
}
async function connect(token) {
  presenterToken = token;
  const rows = await history(); authenticated = true; $('login').hidden = true;
  // Storage is scoped to this origin (including port) and browser tab. Cookies
  // would also be sent to other localhost ports, including an untrusted bank.
  sessionStorage.setItem('rowdy-presenter', presenterToken);
  if (rows.length) await select(rows.find(s => !terminal.has(s.status)) || rows.at(-1));
  render();
}
async function control(kind) {
  if (busy) return;
  busy = true; problem(); buttons();
  try {
    if (!session) await select(await api('/api/assessments', {action_id:actionId(),target_id:'availability-fixture',planner_mode:'fixture'}));
    const snapshot = await api(`/api/assessments/${session.id}/actions`, {type:kind,action_id:actionId()});
    if (snapshot.id !== session.id) await select(snapshot); else { session = snapshot; await refresh(); await history(); }
  } catch (e) { problem(e.message); }
  finally { busy = false; render(); }
}
$('start').onclick = () => control('start');
$('pause').onclick = () => control(session?.allowed_actions.includes('resume') ? 'resume' : 'pause');
$('stop').onclick = () => control('stop');
$('reset').onclick = () => control('reset');
$('history').onchange = async () => { try { await select(await api('/api/assessments/' + $('history').value)); } catch(e) { problem(e.message); } };
$('login-form').onsubmit = async e => { e.preventDefault(); let token = $('token').value; $('token').value = ''; try { await connect(token); problem(); } catch (error) { problem(error.message); } finally { token = ''; } };
$('export').onclick = () => {
  const report = JSON.stringify({format:'rowdy-demo-judge-report/v1',data_source:'fixture',session,events},null,2);
  text('report-json', report); $('report-preview').hidden = false;
  const blob = new Blob([report],{type:'application/json'});
  const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = `${session.id}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
};
(async () => {
  let token = new URLSearchParams(location.hash.slice(1)).get('presenter') || sessionStorage.getItem('rowdy-presenter');
  if (location.hash) window.history.replaceState(null,'',location.pathname);
  try { await connect(token); } catch (e) { $('login').hidden = false; problem('Connect the presenter to start or view a run.'); } finally { token = null; render(); }
  setInterval(async () => {
    if (!authenticated || !session || busy || polling) return;
    polling = true;
    try { const wasTerminal = terminal.has(session.status); await refresh(); if (!wasTerminal && terminal.has(session.status)) await history(); problem(); }
    catch(e) { problem(e.name === 'TimeoutError' ? 'Core did not respond in time. Recovery is not confirmed.' : e.message); text('connection','Connection interrupted'); }
    finally { polling = false; }
  }, 250);
})();
