import Link from 'next/link';
import LiveMonitor from './live-monitor';

export const metadata = {title: 'Live Request Monitor | Rowdy Bank'};

export default function MonitorPage() {
  return <main className="monitor-shell">
    <header className="monitor-header">
      <Link href="/" className="monitor-brand">← &nbsp; Rowdy Bank</Link>
      <span className="monitor-lab-tag">LOCAL SECURITY LAB</span>
    </header>
    <section className="monitor-main">
      <p className="eyebrow">OBSERVABILITY</p>
      <h1>Live request monitor</h1>
      <p className="monitor-intro">Watch HTTP requests reaching the bank app, including the response status and time to respond. Each row is an application request, not a captured network packet.</p>
      <LiveMonitor />
    </section>
    <footer><span>Rowdy Bank</span><span>Local lab · Synthetic traffic metadata</span></footer>
  </main>;
}
