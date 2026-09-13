import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import './admin/tailwind.css';
import StitchShell from './stitch/StitchShell.jsx';
import CoreWorkspaceScreen from './stitch/CoreWorkspaceScreen.jsx';
import DocumentVaultScreen from './stitch/DocumentVaultScreen.jsx';
import MasterKnowledgeScreen from './stitch/MasterKnowledgeScreen.jsx';
import BillingLogsScreen from './stitch/BillingLogsScreen.jsx';
import HumanGatewayScreen from './stitch/HumanGatewayScreen.jsx';
import HumanGatewayModal from './stitch/HumanGatewayModal.jsx';
import AdminDashboard from './admin/AdminDashboard.tsx';

const API = localStorage.getItem('formwise_api') || 'http://localhost:8000';
const uidKey = 'formwise_user';
const getUid = () => { let u = localStorage.getItem(uidKey); if (!u) { u = `demo-${crypto.randomUUID()}`; localStorage.setItem(uidKey, u); } return u; };
const uid = getUid();
const MAX_UPLOAD = 10 * 1024 * 1024;
const ALLOWED = ['application/pdf','image/jpeg','image/png','image/webp'];
const isAdminSurface = new URLSearchParams(window.location.search).get('admin') === '1' || localStorage.getItem('formwise_role') === 'system_admin';

async function api(path, opts = {}) {
  const headers = { 'X-User-ID': uid, ...(opts.headers || {}) };
  if (opts.body && !(opts.body instanceof FormData) && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const response = await fetch(API + path, { ...opts, headers });
  let data = {}; try { data = await response.json(); } catch {}
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

function MaintenanceScreen() {
  return <div className="fw-maintenance"><div className="fw-maintenance-card"><div className="fw-maintenance-logo">↦</div><div className="fw-maintenance-eyebrow">FORMWISE ENTERPRISE AI · CONTROL PLANE</div><h1>System Maintenance</h1><p>The platform is temporarily unavailable while the operations team performs a controlled maintenance cycle. Existing jobs remain protected by server-side safeguards.</p><div className="fw-maintenance-status"><i /> MAINTENANCE MODE ACTIVE <span>ROOT CONTROL</span></div></div></div>;
}

function App() {
  const [view, setView] = useState(new URLSearchParams(window.location.search).get('admin') === '1' ? 'admin' : 'core');
  const [maintenanceMode, setMaintenanceMode] = useState(localStorage.getItem('formwise_maintenance_mode') === 'true');
  const [profile, setProfile] = useState({ full_name:'', date_of_birth:'', gender:'', email:'', phone:'' });
  const [docs, setDocs] = useState([]);
  const [education, setEducation] = useState([]);
  const [addresses, setAddresses] = useState([]);
  const [billing, setBilling] = useState(null);
  const [instruction, setInstruction] = useState('Formwise Demo form bhar do');
  const [workflow, setWorkflow] = useState(null);
  const [approval, setApproval] = useState(null);
  const [screenshot, setScreenshot] = useState('');
  const [gateValue, setGateValue] = useState('');
  const [activeGate, setActiveGate] = useState(null);
  const [resumeRequest, setResumeRequest] = useState(0);
  const [status, setStatus] = useState('Ready');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onMaintenance = event => setMaintenanceMode(Boolean(event.detail?.enabled));
    const onStorage = event => { if (event.key === 'formwise_maintenance_mode') setMaintenanceMode(event.newValue === 'true'); };
    window.addEventListener('formwise:maintenance-mode', onMaintenance);
    window.addEventListener('storage', onStorage);
    return () => { window.removeEventListener('formwise:maintenance-mode', onMaintenance); window.removeEventListener('storage', onStorage); };
  }, []);

  const load = async () => { try { const [p, d, e, a] = await Promise.all([api('/v1/profile'), api('/v1/documents'), api('/v1/education'), api('/v1/addresses')]); setProfile(p); setDocs(d); setEducation(e); setAddresses(a); } catch (e) { setStatus(e.message); } };
  const loadBilling = async () => { try { setBilling(await api('/v1/billing/summary')); } catch { setBilling(null); } };
  useEffect(() => { if (!isAdminSurface) { void load(); void loadBilling(); } }, []);

  const saveProfile = async () => { setBusy(true); try { setProfile(await api('/v1/profile', { method:'PUT', body:JSON.stringify(profile) })); setStatus('Profile saved.'); } catch(e) { setStatus(e.message); } finally { setBusy(false); } };
  const upload = async event => { const file = event?.target?.files?.[0]; if (!file) return; if (file.size > MAX_UPLOAD) { setStatus('Upload rejected: maximum size is 10MB.'); return; } if (!ALLOWED.includes(file.type) && !/\.(pdf|jpe?g|png|webp)$/i.test(file.name)) { setStatus('Upload rejected: allowed types are PDF, JPEG, PNG, WEBP.'); return; } setBusy(true); try { const fd = new FormData(); fd.append('file', file); const d = await api('/v1/documents', { method:'POST', body:fd }); setDocs(x => [d, ...x]); setStatus('Document uploaded securely.'); } catch(e) { setStatus(e.message); } finally { setBusy(false); } };
  const extract = async id => { setBusy(true); try { await api(`/v1/documents/${id}/extract`, { method:'POST' }); await api('/v1/knowledge/reindex', { method:'POST' }); await load(); setStatus('OCR completed and knowledge index refreshed.'); } catch(e) { setStatus(e.message); } finally { setBusy(false); } };
  const start = async () => { setBusy(true); try { const d = await api('/v1/workflows', { method:'POST', body:JSON.stringify({ instruction }) }); setWorkflow(d); setApproval(null); setScreenshot(''); setStatus('Research ready. Review before continuing.'); } catch(e) { setStatus(e.message); } finally { setBusy(false); } };
  const confirm = async confirmed => { if (!workflow) return; setBusy(true); try { const d = await api(`/v1/workflows/${workflow.workflow_id}/confirm`, { method:'POST', body:JSON.stringify({ confirmed }) }); setWorkflow(d); setStatus(d.state === 'documents_missing' ? 'Complete the checklist first.' : 'Documents ready.'); } catch(e) { setStatus(e.message); } finally { setBusy(false); } };
  const openApp = async () => { if (!workflow) return; setBusy(true); try { const d = await api(`/v1/workflows/${workflow.workflow_id}/open`, { method:'POST' }); const p = await api(`/v1/workflows/${d.workflow_id}/plan`, { method:'POST' }); setWorkflow(p); setStatus('Target inspected. Review fields and human gates.'); } catch(e) { setStatus(e.message); } finally { setBusy(false); } };
  const approveField = async item => { if (!workflow) return; setBusy(true); try { const a = await api('/v1/e2e/approvals', { method:'POST', body:JSON.stringify({ session_id:workflow.session_id, item, ttl_seconds:600 }) }); const payload = { index:item.index, field:item.field, value:item.value, session_id:workflow.session_id }; await api(`/v1/approvals/${a.approval_id}/approve`, { method:'POST', body:JSON.stringify({ action:'fill_sensitive', resource_id:workflow.session_id, payload }) }); setWorkflow(p => ({ ...p, fieldApprovals:{ ...(p.fieldApprovals || {}), [item.index]:a.approval_id } })); setStatus(`Approved ${item.field}.`); } catch(e) { setStatus(e.message); } finally { setBusy(false); } };
  const refreshShot = async currentWorkflow => { try { const response = await fetch(`${API}/v1/workflows/${currentWorkflow.workflow_id}/screenshot`, { headers:{'X-User-ID':uid}, cache:'no-store' }); if (response.ok) { if (screenshot) URL.revokeObjectURL(screenshot); setScreenshot(URL.createObjectURL(await response.blob())); } } catch {} };
  const fill = async () => { if (!workflow) return; setBusy(true); try { const fills = (workflow.plan?.fills || []).filter(x => !x.requires_approval || workflow.fieldApprovals?.[x.index]).map(x => ({ ...x, approval_id:workflow.fieldApprovals?.[x.index] })); const d = await api(`/v1/workflows/${workflow.workflow_id}/fill`, { method:'POST', body:JSON.stringify({ fills }) }); setWorkflow(d); await refreshShot(d); setStatus(d.state === 'final_review' ? 'All automated fields filled. Final review required.' : 'Approved fields filled.'); } catch(e) { setStatus(e.message); } finally { setBusy(false); } };
  const finalApproval = async () => { if (!workflow) return; setBusy(true); try { const a = await api(`/v1/workflows/${workflow.workflow_id}/final-approval`, { method:'POST' }); setApproval(a); setStatus('Final approval prepared. Review the live form carefully.'); } catch(e) { setStatus(e.message); } finally { setBusy(false); } };
  const finalSubmit = async () => { if (!workflow || !approval?.approval_id) return; setBusy(true); try { const d = await api(`/v1/workflows/${workflow.workflow_id}/submit`, { method:'POST', body:JSON.stringify({ approval_id:approval.approval_id }) }); setWorkflow(d); await refreshShot(d); setStatus('Submitted only after explicit final approval.'); } catch(e) { setStatus(e.message); } finally { setBusy(false); } };
  const onHumanGate = gate => { setActiveGate(gate); setView('core'); };
  const onLiveControl = state => { if (state.control === 'locked' && state.mode === 'ai' && !state.paused) setActiveGate(null); };
  const resumeHuman = () => { setResumeRequest(x => x + 1); setGateValue(''); };

  if (!isAdminSurface && maintenanceMode) return <MaintenanceScreen />;
  if (view === 'admin') return <AdminDashboard />;

  const renderView = () => {
    if (view === 'vault') return <DocumentVaultScreen docs={docs} busy={busy} onUpload={upload} onExtract={extract} />;
    if (view === 'knowledge') return <MasterKnowledgeScreen profile={profile} education={education} addresses={addresses} />;
    if (view === 'billing') return <BillingLogsScreen billing={billing} busy={busy} onRefresh={loadBilling} />;
    if (view === 'human') return <HumanGatewayScreen gate={activeGate} onClose={() => setView('core')} />;
    return <CoreWorkspaceScreen apiBase={API} userId={uid} workflow={workflow} instruction={instruction} setInstruction={setInstruction} busy={busy} status={status} docs={docs} onStart={start} onConfirm={confirm} onOpen={openApp} onUpload={upload} onExtract={extract} onApprove={approveField} onFill={fill} onFinalApproval={finalApproval} onFinalSubmit={finalSubmit} approval={approval} screenshot={screenshot} onHumanGate={onHumanGate} onLiveControl={onLiveControl} resumeRequest={resumeRequest} />;
  };

  return <StitchShell view={view} onNavigate={setView} status={status}>{renderView()}{activeGate && <HumanGatewayModal gate={activeGate} gateValue={gateValue} setGateValue={setGateValue} onResume={resumeHuman} onCancel={() => setView('human')} busy={busy} />}</StitchShell>;
}

createRoot(document.getElementById('root')).render(<App />);
