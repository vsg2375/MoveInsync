import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, ArrowUpRight, BadgeCheck, BookOpen, Bot, Building2, Check,
  ChevronDown, CircleHelp, Clock3, FileCheck2, FilePlus2, FileText,
  KeyRound, LifeBuoy, LoaderCircle, LockKeyhole, LogOut, MessageSquare,
  Paperclip, Plane, Plus, Send, ShieldCheck, Sparkles, UploadCloud,
  UserRound, Users, X, Zap,
} from 'lucide-react';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const COMPANIES = [
  { id: 'technova', name: 'TechNova', initials: 'TN', color: 'violet' },
  { id: 'datasphere', name: 'DataSphere', initials: 'DS', color: 'blue' },
  { id: 'cloudaxis', name: 'CloudAxis', initials: 'CA', color: 'orange' },
];
const STARTER_QUESTIONS = [
  'What is the minimum booking notice for a standard commute?',
  'What are the night-shift escort rules?',
  'Can I book transport on a Saturday?',
  'What happens if I miss my scheduled cab?',
];

async function apiRequest(path, options = {}) {
  const { token, ...fetchOptions } = options;
  const headers = new Headers(fetchOptions.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (fetchOptions.body && !(fetchOptions.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers });
  } catch {
    throw new Error(`Cannot reach the CommuteIQ API at ${API_BASE}. Start the backend and try again.`);
  }
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = payload && typeof payload === 'object' ? payload.detail : payload;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return payload;
}

function BrandMark({ small = false }) {
  return <div className={`brand-mark${small ? ' small' : ''}`}><Activity size={small ? 17 : 20} strokeWidth={2.6} /></div>;
}

function renderAnswer(text) {
  const parts = String(text || '').split(/\\?\*\*(.+?)\\?\*\*/g);
  return parts.map((part, index) => index % 2 === 1 ? <strong key={index}>{part}</strong> : part);
}

function App() {
  const [apiStatus, setApiStatus] = useState('checking');
  const [employeeId, setEmployeeId] = useState('emp-101');
  const [companyId, setCompanyId] = useState('technova');
  const [session, setSession] = useState(null);
  const [activeView, setActiveView] = useState('assistant');
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [signingIn, setSigningIn] = useState(false);
  const [notice, setNotice] = useState(null);
  const [adminToken, setAdminToken] = useState('');
  const [adminPolicies, setAdminPolicies] = useState([]);
  const [adminLoading, setAdminLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadForm, setUploadForm] = useState({ company_id: 'technova', version: '', document: '', effective_date: '' });
  const [policyFile, setPolicyFile] = useState(null);
  const [adminNotice, setAdminNotice] = useState(null);
  const chatEndRef = useRef(null);
  const questionRef = useRef(null);

  const selectedCompany = useMemo(() => COMPANIES.find((c) => c.id === companyId) || COMPANIES[0], [companyId]);

  useEffect(() => {
    let active = true;
    const checkApi = () => apiRequest('/health')
      .then(() => { if (active) setApiStatus('online'); })
      .catch(() => { if (active) setApiStatus('offline'); });
    checkApi();
    const interval = window.setInterval(checkApi, 5000);
    return () => { active = false; window.clearInterval(interval); };
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, busy]);

  async function handleSignIn(event) {
    event.preventDefault();
    setNotice(null);
    setSigningIn(true);
    try {
      const result = await apiRequest('/auth/demo-token', {
        method: 'POST',
        body: JSON.stringify({ employee_id: employeeId.trim(), company_id: companyId }),
      });
      if (!result.access_token) throw new Error('The API did not return an access token.');
      setSession({ token: result.access_token, employeeId: employeeId.trim(), companyId });
      setMessages([]);
      setNotice({ type: 'success', text: `Signed in to ${selectedCompany.name}. Your questions will be scoped to this company.` });
      setActiveView('assistant');
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    } finally {
      setSigningIn(false);
    }
  }

  function signOut() {
    setSession(null);
    setMessages([]);
    setQuestion('');
    setNotice({ type: 'info', text: 'You have signed out.' });
  }

  async function sendQuestion(text = question) {
    const clean = text.trim();
    if (!clean || busy) return;
    if (!session?.token) {
      setNotice({ type: 'error', text: 'Sign in as an employee before asking a policy question.' });
      return;
    }
    setQuestion('');
    setNotice(null);
    const userMessage = { id: crypto.randomUUID(), role: 'user', content: clean };
    setMessages((current) => [...current, userMessage]);
    setBusy(true);
    try {
      const answer = await apiRequest('/ask', {
        method: 'POST',
        token: session.token,
        body: JSON.stringify({ question: clean }),
      });
      setMessages((current) => [...current, {
        id: crypto.randomUUID(), role: 'assistant', content: answer.answer || 'The assistant returned an empty answer.',
        covered: Boolean(answer.covered), citations: answer.citations || [], version: answer.version,
        companyId: answer.company_id || session.companyId,
      }]);
    } catch (error) {
      setMessages((current) => [...current, {
        id: crypto.randomUUID(), role: 'error', content: error.message,
      }]);
    } finally {
      setBusy(false);
      questionRef.current?.focus();
    }
  }

  async function loadAdminPolicies(token = adminToken) {
    if (!token.trim()) {
      setAdminNotice({ type: 'error', text: 'Paste an admin JWT first.' });
      return;
    }
    setAdminLoading(true);
    setAdminNotice(null);
    try {
      const result = await apiRequest('/admin/policies', { token: token.trim() });
      setAdminPolicies(Array.isArray(result) ? result : []);
      setAdminNotice({ type: 'success', text: `Loaded ${(Array.isArray(result) ? result : []).length} policy records.` });
    } catch (error) {
      setAdminNotice({ type: 'error', text: error.message });
    } finally {
      setAdminLoading(false);
    }
  }

  async function uploadPolicy(event) {
    event.preventDefault();
    if (!adminToken.trim()) return setAdminNotice({ type: 'error', text: 'Paste an admin JWT first.' });
    if (!policyFile) return setAdminNotice({ type: 'error', text: 'Choose a PDF policy document.' });
    if (!uploadForm.version.trim() || !uploadForm.document.trim()) return setAdminNotice({ type: 'error', text: 'Enter a policy version and document name.' });
    setUploading(true);
    setAdminNotice(null);
    try {
      const params = new URLSearchParams({
        company_id: uploadForm.company_id,
        version: uploadForm.version.trim(),
        document: uploadForm.document.trim(),
      });
      if (uploadForm.effective_date.trim()) params.set('effective_date', uploadForm.effective_date.trim());
      const form = new FormData();
      form.append('file', policyFile);
      const result = await apiRequest(`/admin/policies/upload?${params.toString()}`, {
        method: 'POST', token: adminToken.trim(), body: form,
      });
      setAdminNotice({ type: 'success', text: `Policy version ${result.version} is now active for ${result.company_id}. Indexed ${result.chunks} sections.` });
      setPolicyFile(null);
      setUploadForm((current) => ({ ...current, version: '', document: '', effective_date: '' }));
      await loadAdminPolicies(adminToken.trim());
    } catch (error) {
      setAdminNotice({ type: 'error', text: error.message });
    } finally {
      setUploading(false);
    }
  }

  const activeCompany = session ? COMPANIES.find((c) => c.id === session.companyId) : selectedCompany;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup"><BrandMark /><div><div className="brand-name">commute<span>iq</span></div><div className="brand-caption">POLICY INTELLIGENCE</div></div></div>
        <div className="workspace-label">WORKSPACE</div>
        <button className={`nav-item ${activeView === 'assistant' ? 'active' : ''}`} onClick={() => setActiveView('assistant')}><MessageSquare size={17} /> Policy assistant <span className="nav-dot" /></button>
        <button className={`nav-item ${activeView === 'admin' ? 'active' : ''}`} onClick={() => setActiveView('admin')}><FileCheck2 size={17} /> Policy management <span className="nav-admin-tag">ADMIN</span></button>
        <div className="sidebar-divider" />
        <div className="workspace-label">YOUR ORGANISATION</div>
        <div className="org-card">
          <div className={`org-avatar ${activeCompany?.color || 'violet'}`}>{activeCompany?.initials || 'TN'}</div>
          <div className="org-copy"><strong>{session ? activeCompany?.name : 'No active session'}</strong><span>{session ? `Employee · ${session.employeeId}` : 'Sign in to get started'}</span></div>
          <ChevronDown size={15} className="muted-icon" />
        </div>
        <div className="sidebar-spacer" />
        <div className="sidebar-help"><div className="help-icon"><LifeBuoy size={17} /></div><div><strong>Need a hand?</strong><span>Contact your transport desk for policy clarification.</span></div></div>
        <div className="sidebar-footer"><span className="status-pip" /> Demo environment <span className="footer-version">v1.0.0</span></div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><span className="crumb-slash">/</span><strong>{activeView === 'assistant' ? 'Policy assistant' : 'Policy administration'}</strong></div>
          <div className="topbar-right">
            <div className={`api-indicator ${apiStatus}`}><span />{apiStatus === 'checking' ? 'Checking API' : apiStatus === 'online' ? 'API connected' : 'API offline'}</div>
            {session ? <button className="profile-button" onClick={signOut} title="Sign out"><span className="profile-avatar"><UserRound size={15} /></span><span>{session.employeeId}</span><LogOut size={15} /></button> : <span className="demo-pill"><ShieldCheck size={13} /> Local demo</span>}
          </div>
        </header>

        {activeView === 'assistant' ? (
          <div className={`content-wrap assistant-wrap ${!session ? 'signed-out-wrap' : ''}`}>
            <div className="page-heading"><div><div className="eyebrow"><Sparkles size={13} /> YOUR COMMUTE, CLARIFIED</div><h1>Commute policy <span>assistant</span></h1><p>Get clear answers from your company's current transport policy, with sources you can verify.</p></div><div className="heading-mark"><BookOpen size={22} /><span>Grounded in policy</span></div></div>

            {notice && <div className={`notice ${notice.type}`}><span>{notice.type === 'success' ? <Check size={16} /> : <CircleHelp size={16} />}</span>{notice.text}<button onClick={() => setNotice(null)} aria-label="Dismiss"><X size={15} /></button></div>}

            {!session ? (
              <section className="signin-card">
                <div className="signin-art"><div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" /><div className="art-center"><BrandMark /></div><div className="art-floating art-float-one"><ShieldCheck size={18} /></div><div className="art-floating art-float-two"><FileText size={17} /></div><div className="art-line art-line-one" /><div className="art-line art-line-two" /></div>
                <div className="signin-form-wrap"><div className="section-kicker">EMPLOYEE SIGN IN</div><h2>Welcome back</h2><p className="muted-copy">Choose your company and enter your employee ID to ask policy questions.</p>
                  <form className="signin-form" onSubmit={handleSignIn}>
                    <label>Employee ID<div className="field-wrap"><UserRound size={16} /><input value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} placeholder="e.g. emp-101" minLength={1} maxLength={80} required /></div></label>
                    <label>Company<div className="field-wrap"><Building2 size={16} /><select value={companyId} onChange={(e) => setCompanyId(e.target.value)}>{COMPANIES.map((company) => <option value={company.id} key={company.id}>{company.name}</option>)}</select><ChevronDown size={15} className="select-chevron" /></div></label>
                    <button className="primary-button signin-button" disabled={signingIn || apiStatus === 'offline'}>{signingIn ? <LoaderCircle className="spin" size={17} /> : <LockKeyhole size={16} />} {signingIn ? 'Signing in…' : 'Continue as employee'} <ArrowUpRight size={16} /></button>
                  </form>
                  <div className="signin-foot"><ShieldCheck size={14} /> Your company is taken from your signed token, not from the question.</div>
                </div>
              </section>
            ) : (
              <section className="chat-layout">
                <div className="chat-main">
                  <div className="chat-context"><div className="context-icon"><Building2 size={17} /></div><div><strong>{activeCompany?.name} transport policy</strong><span>Answers are restricted to your active company policy</span></div><span className="secure-tag"><LockKeyhole size={12} /> Private</span></div>
                  <div className="chat-scroll">
                    {messages.length === 0 ? <div className="welcome-state"><div className="welcome-icon"><Bot size={25} /></div><div className="section-kicker">YOUR POLICY COPILOT</div><h2>How can I help with<br />your commute?</h2><p>Ask a question about eligibility, shifts, bookings or transport rules. I'll show you the policy section behind the answer.</p><div className="suggestion-grid">{STARTER_QUESTIONS.map((item, index) => <button className="suggestion-card" key={item} onClick={() => sendQuestion(item)}><span className={`suggestion-icon suggestion-${index}`}><Zap size={15} /></span><span>{item}</span><ArrowUpRight size={15} className="suggestion-arrow" /></button>)}</div></div> : <div className="message-list">{messages.map((message) => <article className={`message-row ${message.role}`} key={message.id}><div className={`message-avatar ${message.role}`}>{message.role === 'user' ? <UserRound size={16} /> : message.role === 'error' ? <CircleHelp size={16} /> : <Bot size={17} />}</div><div className="message-body"><div className="message-meta"><strong>{message.role === 'user' ? 'You' : message.role === 'error' ? 'Connection issue' : 'CommuteIQ'}</strong><span>{message.role === 'assistant' ? 'Policy-grounded response' : message.role === 'error' ? 'Please try again' : 'Your question'}</span></div><div className={`message-bubble ${message.role}`}>{message.role === 'assistant' ? renderAnswer(message.content) : message.content}</div>{message.role === 'assistant' && <><div className={`answer-status ${message.covered ? 'covered' : 'not-covered'}`}><span>{message.covered ? <BadgeCheck size={13} /> : <LifeBuoy size={13} />}</span>{message.covered ? 'Answer found in policy' : 'Not covered by current policy'}{message.version && <span className="version-tag">Version {message.version}</span>}</div>{message.citations?.length > 0 && <div className="citations-block"><div className="citation-heading"><BookOpen size={13} /> POLICY SOURCES <span>{message.citations.length} {message.citations.length === 1 ? 'source' : 'sources'}</span></div>{message.citations.map((citation, idx) => <div className="citation-item" key={`${citation.document}-${citation.section}-${idx}`}><div className="citation-file"><FileText size={15} /></div><div><strong>{citation.document}</strong><span>{citation.section}</span></div><Check size={14} className="citation-check" /></div>)}</div>}</>}</div></article>)}{busy && <div className="message-row assistant"><div className="message-avatar assistant"><Bot size={17} /></div><div className="message-body"><div className="message-meta"><strong>CommuteIQ</strong><span>Searching your policy</span></div><div className="typing-bubble"><i /><i /><i /></div></div></div>}<div ref={chatEndRef} /></div>}
                  </div>
                  <form className="composer" onSubmit={(e) => { e.preventDefault(); sendQuestion(); }}><div className="composer-inner"><input ref={questionRef} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask anything about your commute policy…" maxLength={1000} disabled={busy} /><span className="composer-shortcut">↵</span><button className="send-button" disabled={!question.trim() || busy} aria-label="Send question">{busy ? <LoaderCircle size={17} className="spin" /> : <Send size={17} />}</button></div><div className="composer-caption"><span><LockKeyhole size={11} /> Company-scoped retrieval</span><span>{question.length}/1000</span></div></form>
                </div>
                <aside className="chat-aside"><div className="aside-card policy-card"><div className="aside-card-head"><span className="aside-icon lavender"><FileCheck2 size={16} /></span><span className="live-label"><i /> ACTIVE POLICY</span></div><h3>{activeCompany?.name}</h3><p>Only the latest active policy version is used to answer your questions.</p><div className="aside-divider" /><div className="aside-stat"><span>Access scope</span><strong><LockKeyhole size={13} /> Your company only</strong></div><div className="aside-stat"><span>Employee</span><strong>{session.employeeId}</strong></div><div className="aside-stat"><span>Answer sources</span><strong>Up to 3 sections</strong></div></div><div className="aside-card trust-card"><div className="trust-title"><ShieldCheck size={17} /> Built for trustworthy answers</div><div className="trust-feature"><span><Check size={13} /></span><div><strong>Company isolation</strong><small>Other organisations' policies stay out of your results.</small></div></div><div className="trust-feature"><span><Check size={13} /></span><div><strong>Verifiable sources</strong><small>Every covered answer includes document and section references.</small></div></div><div className="trust-feature"><span><Check size={13} /></span><div><strong>Honest when unsure</strong><small>Uncovered questions are referred to your transport desk.</small></div></div></div><div className="aside-note"><LifeBuoy size={15} /><span>For urgent transport changes or exceptions, contact your transport desk directly.</span></div></aside>
              </section>
            )}
            <footer className="page-footer"><span>© 2026 CommuteIQ</span><span>Policy answers are informational. Your company's official policy remains authoritative.</span></footer>
          </div>
        ) : (
          <div className="content-wrap admin-wrap">
            <div className="page-heading"><div><div className="eyebrow"><FileCheck2 size={13} /> POLICY CONTROL CENTRE</div><h1>Policy <span>management</span></h1><p>Administrator workspace: upload a new company policy version and review active or previous versions. Employees do not need this page.</p></div><div className="heading-mark"><ShieldCheck size={22} /><span>Admin access required</span></div></div>
            <div className="admin-warning"><KeyRound size={17} /><div><strong>Local demo administrator access</strong><p>Generate an admin JWT using <code>python scripts/create_admin_token.py --employee-id admin-1 --company-id technova</code> in the project root, then paste it below. Employee tokens cannot access these controls.</p></div></div>
            <section className="admin-token-card"><label>Admin bearer token<textarea value={adminToken} onChange={(e) => setAdminToken(e.target.value)} placeholder="Paste the admin access token here" rows={2} /></label><div className="admin-token-actions"><span><LockKeyhole size={13} /> Token is kept in this browser tab only.</span><button className="secondary-button" onClick={() => loadAdminPolicies()} disabled={adminLoading}>{adminLoading ? <LoaderCircle size={15} className="spin" /> : <Activity size={15} />} Load policy records</button></div>{adminNotice && <div className={`notice compact ${adminNotice.type}`}>{adminNotice.text}</div>}</section>
            <div className="admin-grid"><section className="admin-panel"><div className="panel-heading"><div><div className="section-kicker">INGESTION</div><h2>Upload a new policy</h2><p>A successful upload activates the new version for the selected company.</p></div><span className="panel-icon"><UploadCloud size={19} /></span></div><form className="upload-form" onSubmit={uploadPolicy}><label>Company<select value={uploadForm.company_id} onChange={(e) => setUploadForm({ ...uploadForm, company_id: e.target.value })}>{COMPANIES.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}</select></label><div className="form-two-col"><label>New version<input value={uploadForm.version} onChange={(e) => setUploadForm({ ...uploadForm, version: e.target.value })} placeholder="e.g. 3.0" required /></label><label>Effective date<input type="date" value={uploadForm.effective_date} onChange={(e) => setUploadForm({ ...uploadForm, effective_date: e.target.value })} /></label></div><label>Document name<input value={uploadForm.document} onChange={(e) => setUploadForm({ ...uploadForm, document: e.target.value })} placeholder="e.g. technova_policy_v3.pdf" required /></label><label className="file-drop"><input type="file" accept="application/pdf,.pdf" onChange={(e) => setPolicyFile(e.target.files?.[0] || null)} /><span className="file-drop-icon"><Paperclip size={17} /></span><span><strong>{policyFile ? policyFile.name : 'Choose a PDF policy document'}</strong><small>{policyFile ? `${(policyFile.size / 1024 / 1024).toFixed(2)} MB · PDF` : 'PDF only · Maximum 5 MB'}</small></span><span className="browse-link">Browse</span></label><button className="primary-button upload-button" disabled={uploading}>{uploading ? <LoaderCircle className="spin" size={16} /> : <FilePlus2 size={16} />}{uploading ? 'Uploading and indexing…' : 'Upload and activate policy'}</button></form></section>
              <section className="admin-panel policies-panel"><div className="panel-heading"><div><div className="section-kicker">POLICY REGISTER</div><h2>Stored policy versions</h2><p>Review active and historical policy records.</p></div><span className="panel-icon"><BookOpen size={19} /></span></div>{adminPolicies.length === 0 ? <div className="empty-policies"><div><FileText size={22} /></div><strong>No policy records loaded</strong><span>Paste an admin token and load policy records to view the register.</span></div> : <div className="policy-table-wrap"><table className="policy-table"><thead><tr><th>Company</th><th>Document / version</th><th>Status</th></tr></thead><tbody>{adminPolicies.map((policy) => <tr key={`${policy.company_id}-${policy.version}`}><td><strong>{COMPANIES.find((c) => c.id === policy.company_id)?.name || policy.company_id}</strong></td><td><span>{policy.document}</span><small>v{policy.version}</small></td><td><span className={`policy-state ${policy.status}`}>{policy.status}</span></td></tr>)}</tbody></table></div>}</section></div>
            <footer className="page-footer"><span>© 2026 CommuteIQ</span><span>Only authorised admin tokens can ingest or list policies.</span></footer>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
