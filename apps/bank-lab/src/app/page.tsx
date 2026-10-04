'use client';
import Image from 'next/image';
import {useEffect, useState, type FormEvent} from 'react';

type User = {display_name: string; username: string; role: string};
type Account = {account_id: string; label: string; balance_cents: number};
type Vault = {vault_id: string; label: string; synthetic_record: string};
const money = (cents: number) => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(cents / 100);
class ApiError extends Error {
  constructor(message: string, public status: number) {super(message);}
}
async function api(path: string, method = 'GET', body?: unknown) {
  const response = await fetch('/api/' + path, {method, cache: 'no-store',
    ...(body ? {headers: {'content-type': 'application/json'}, body: JSON.stringify(body)} : {})});
  const data = await response.json();
  if (!response.ok) throw new ApiError(data.error || 'Bank is not ready yet', response.status);
  return data;
}
export default function Bank() {
  const [user, setUser] = useState<User | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [vault, setVault] = useState<Vault[] | null>(null);
  const [vaultDenied, setVaultDenied] = useState(false);
  const [health, setHealth] = useState('Checking connection');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [section, setSection] = useState('accounts');
  useEffect(() => {
    api('health').then(() => setHealth('Bank ready')).catch(() => setHealth('Setup required'));
    api('me').then(async data => {setUser(data.user); setAccounts((await api('accounts')).accounts);}).catch(() => {});
  }, []);
  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage('');
    const form = event.currentTarget;
    const values = new FormData(form);
    try {
      await api('login', 'POST', {username: values.get('username'), password: values.get('password')});
      form.reset();
      setUser((await api('me')).user);
      setAccounts((await api('accounts')).accounts);
      setHealth('Bank ready');
    } catch (error) { setMessage((error as Error).message); }
    finally {setBusy(false);}
  }
  async function openVault() {
    setSection('vault'); setMessage(''); setVault(null); setVaultDenied(false); setBusy(true);
    try {setVault((await api('vault')).records);}
    catch (error) {
      setVaultDenied(error instanceof ApiError && [401, 403].includes(error.status));
      setMessage((error as Error).message);
    }
    finally {setBusy(false);}
  }
  async function signOut() {
    setBusy(true); setMessage('');
    try {await api('logout', 'POST'); setUser(null); setAccounts([]); setVault(null); setSection('accounts');}
    catch (error) {setMessage((error as Error).message);}
    finally {setBusy(false);}
  }
  return <div className="shell">
    <header className="topbar"><a className="brand" href="/" aria-label="Rowdy Bank home"><Image className="brand-mark" src="/utsa-roadrunner.png" alt="" width={58} height={58} priority /> <span>Rowdy Bank</span></a>
      <div className="header-right"><a className="monitor-nav" href="/monitor">Live monitor ↗</a><span className="lab-tag">Synthetic bank</span><span className="health"><i />{health}</span></div>
    </header>
    {!user ? <main className="welcome">
      <section className="intro"><p className="eyebrow">ROWDYHACKS SECURITY LAB</p><h1>Banking meets<br />security practice.</h1>
        <p className="intro-text">Rowdy Bank is a fictional bank built for the RowdyHacks security challenge. Sign in with your assigned synthetic account to view balances and explore protected records. No real money or customer data is used.</p>
        <div className="bank-illustration" aria-hidden="true"><div className="roof"/><div className="pillars"><span/><span/><span/><span/></div><div className="steps"/><span className="seal">B</span></div>
        <p className="caption">A controlled environment for learning and testing</p>
      </section>
      <section className="login-card"><p className="eyebrow">ACCOUNT ACCESS</p><h2>Sign in to Rowdy Bank</h2><p className="muted">Use the lab credentials assigned to you.</p>
        <form onSubmit={signIn}>
          <label htmlFor="username">Username</label><input id="username" name="username" autoComplete="username" maxLength={64} required />
          <label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" maxLength={256} required />
          <button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in →'}</button>
        </form>
        {message && <p className="message" role="alert">{message}</p>}
        <p className="login-note">This training site uses synthetic accounts and balances.</p>
      </section>
    </main> : <main className="dashboard">
      <aside><p className="eyebrow">WORKSPACE</p><button className={section === 'accounts' ? 'nav active' : 'nav'} onClick={() => {setSection('accounts'); setMessage('');}}>◫ &nbsp; Accounts</button>
        <button className={section === 'vault' ? 'nav active' : 'nav'} onClick={openVault} disabled={busy}>◇ &nbsp; Vault</button>
        <div className="identity"><span>{user.display_name}</span><small>{user.username}</small><button onClick={signOut} disabled={busy}>Sign out</button></div>
      </aside>
      <section className="workspace"><p className="eyebrow">{section === 'accounts' ? 'ACCOUNT OVERVIEW' : 'PROTECTED RECORDS'}</p>
        <h1>{section === 'accounts' ? `Hello, ${user.display_name}.` : 'The vault'}</h1>
        <p className="muted">{section === 'accounts' ? 'Your synthetic accounts, all in one place.' : 'Vault records require server-side authorization.'}</p>
        {section === 'accounts' ? <><div className="balance-card"><span>Total balance</span><strong>{money(accounts.reduce((sum, account) => sum + account.balance_cents, 0))}</strong><small>Synthetic funds · USD</small></div>
          <h2>Your accounts</h2><div className="accounts">{accounts.map(account => <article className="account" key={account.account_id}><div><h3>{account.label}</h3><p>Account · {account.account_id}</p></div><strong>{money(account.balance_cents)}</strong></article>)}</div></>
          : <div className="vault-panel"><span className="vault-symbol" aria-hidden="true">◇</span>{busy ? <p>Checking authorization…</p> : vault ? vault.map(record => <article key={record.vault_id}><h2>{record.label}</h2><p className="vault-record">{record.synthetic_record}</p></article>) : vaultDenied ? <><h2>Access restricted</h2><p className="muted">This session cannot view protected vault records.</p></> : <><h2>Vault unavailable</h2><p className="muted">The bank could not complete this request. Try again after checking its connection.</p></>}</div>}
        {message && <p className="message" role="alert">{message}</p>}
      </section>
    </main>}
    <footer><span>Rowdy Bank</span><span>Synthetic data · Controlled environment</span><span>RowdyHacks security challenge</span></footer>
  </div>;
}
