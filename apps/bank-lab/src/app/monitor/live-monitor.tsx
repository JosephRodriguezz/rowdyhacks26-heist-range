'use client';

import {useEffect, useMemo, useState} from 'react';

type RequestLog = {
  sequence: number;
  timestamp: string;
  method: 'GET' | 'POST';
  route: string;
  status: number;
  durationMs: number;
};

export default function LiveMonitor() {
  const [logs, setLogs] = useState<RequestLog[]>([]);
  const [cursor, setCursor] = useState(0);
  const [connected, setConnected] = useState(false);
  const recentCount = useMemo(() => {
    const cutoff = Date.now() - 60_000;
    return logs.filter(log => Date.parse(log.timestamp) >= cutoff).length;
  }, [logs]);

  useEffect(() => {
    let active = true;
    let current = 0;
    const poll = async () => {
      try {
        const response = await fetch(`/api/monitor/logs?after=${current}`, {cache: 'no-store'});
        if (!response.ok) throw new Error('Monitor unavailable');
        const data = await response.json() as {events: RequestLog[]; latest: number};
        if (!active) return;
        if (Array.isArray(data.events) && data.events.length) {
          setLogs(existing => [...existing, ...data.events].slice(-100));
          current = data.latest;
          setCursor(current);
        }
        setConnected(true);
      } catch {
        if (active) setConnected(false);
      }
    };
    void poll();
    const interval = window.setInterval(poll, 1000);
    return () => {active = false; window.clearInterval(interval);};
  }, []);

  return <>
    <div className="monitor-stats">
      <article><span>Requests · last minute</span><strong>{recentCount}</strong></article>
      <article><span>Captured in this view</span><strong>{logs.length}</strong></article>
      <article><span>Stream status</span><strong className={connected ? 'stream-live' : 'stream-offline'}><i />{connected ? 'Live' : 'Reconnecting'}</strong></article>
    </div>
    <section className="log-panel" aria-label="Live HTTP request log">
      <div className="log-panel-heading"><div><h2>Request stream</h2><p>Latest first · capped in memory · polling once per second</p></div><span>Cursor {cursor}</span></div>
      <div className="log-scroll">
        <table>
          <thead><tr><th>Time</th><th>Method</th><th>Route</th><th>Status</th><th>Latency</th></tr></thead>
          <tbody>{[...logs].reverse().map(log => <tr key={log.sequence}>
            <td>{new Date(log.timestamp).toLocaleTimeString()}</td>
            <td><span className="method-pill">{log.method}</span></td>
            <td className="route-cell">{log.route}</td>
            <td><span className={`status-pill ${log.status >= 500 ? 'status-error' : log.status >= 400 ? 'status-warn' : 'status-ok'}`}>{log.status}</span></td>
            <td>{log.durationMs} ms</td>
          </tr>)}</tbody>
        </table>
        {logs.length === 0 && <p className="log-empty">Waiting for bank requests. Open the bank in another tab, sign in, or run the local training search to create activity.</p>}
      </div>
    </section>
    <p className="monitor-note">For a bounded availability demonstration, use only this local lab and a low request rate. This monitor records route, status, and latency; it does not capture packet contents, source addresses, query strings, credentials, cookies, or request bodies.</p>
  </>;
}
