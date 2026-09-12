import React,{useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const API=localStorage.getItem('formwise_api')||'http://localhost:8000';
const uidKey='formwise_user';
const getUid=()=>{let u=localStorage.getItem(uidKey);if(!u){u='demo-'+crypto.randomUUID();localStorage.setItem(uidKey,u)}return u};
const uid=getUid();
async function api(path,opts={}){const h={'X-User-ID':uid,...(opts.headers||{})};if(opts.body&&!h['Content-Type'])h['Content-Type']='application/json';const r=await fetch(API+path,{...opts,headers:h});let d={};try{d=await r.json()}catch{}if(!r.ok)throw Error(d.detail||`Request failed (${r.status})`);return d}

function App(){
 const [profile,setProfile]=useState({full_name:'',date_of_birth:'',gender:'',email:'',phone:''});
 const [docs,setDocs]=useState([]); const [url,setUrl]=useState(''); const [session,setSession]=useState('');
 const [instruction,setInstruction]=useState('SSC ka form bhar do'); const [plan,setPlan]=useState(null); const [status,setStatus]=useState('Ready'); const [busy,setBusy]=useState(false);
 const load=async()=>{try{setProfile(await api('/v1/profile'));setDocs(await api('/v1/documents'))}catch(e){setStatus(e.message)}};
 useEffect(()=>{load()},[]);
 const saveProfile=async()=>{setBusy(true);try{setProfile(await api('/v1/profile',{method:'PUT',body:JSON.stringify(profile)}));setStatus('Profile saved')}catch(e){setStatus(e.message)}finally{setBusy(false)}};
 const upload=async e=>{const f=e.target.files?.[0];if(!f)return;setBusy(true);try{let fd=new FormData();fd.append('file',f);let r=await fetch(API+'/v1/documents',{method:'POST',headers:{'X-User-ID':uid},body:fd});let d=await r.json();if(!r.ok)throw Error(d.detail);setDocs(x=>[d,...x]);setStatus('Document uploaded. Extract it from the Documents panel.')}catch(e){setStatus(e.message)}finally{setBusy(false)}};
 const extract=async id=>{setBusy(true);try{await api(`/v1/documents/${id}/extract`,{method:'POST'});await load();setStatus('Document extracted and indexed.')}catch(e){setStatus(e.message)}finally{setBusy(false)}};
 const start=async()=>{setBusy(true);try{let d=await api('/v1/browser/sessions',{method:'POST',body:'{}'});setSession(d.session_id);await api(`/v1/browser/sessions/${d.session_id}/navigate`,{method:'POST',body:JSON.stringify({url})});setStatus('Website opened.');}catch(e){setStatus(e.message)}finally{setBusy(false)}};
 const makePlan=async()=>{setBusy(true);try{setPlan(await api('/v1/e2e/plan',{method:'POST',body:JSON.stringify({session_id:session,instruction})}));setStatus('Plan ready — review before filling.')}catch(e){setStatus(e.message)}finally{setBusy(false)}};
 const approve=async item=>{setBusy(true);try{let a=await api('/v1/e2e/approvals',{method:'POST',body:JSON.stringify({session_id:session,item,ttl_seconds:600})});const payload={index:item.index,field:item.field,value:item.value,session_id:session};await api(`/v1/approvals/${a.approval_id}/approve`,{method:'POST',body:JSON.stringify({action:'fill_sensitive',resource_id:session,payload})});setPlan(p=>({...p,approvalIds:{...(p.approvalIds||{}),[item.index]:a.approval_id}}));setStatus('Approved. Click Fill when all required approvals are done.')}catch(e){setStatus(e.message)}finally{setBusy(false)}};
 const fill=async()=>{setBusy(true);try{let fills=(plan?.fills||[]).filter(x=>!x.requires_approval||plan?.approvalIds?.[x.index]).map(x=>({...x,approval_id:plan?.approvalIds?.[x.index]}));let d=await api('/v1/e2e/fill',{method:'POST',body:JSON.stringify({session_id:session,fills})});setPlan(p=>({...p,result:d}));setStatus('Fields filled. Final submission remains blocked for human review.')}catch(e){setStatus(e.message)}finally{setBusy(false)}};
 return <div className="app"><header><div><b>Formwise</b><span> Agent</span><p>Privacy-first form filling</p></div><div className="pill">{status}</div></header>
 <main><section className="hero"><h1>Your forms, filled safely.</h1><p>Store verified personal information once, then let Formwise prepare supported online forms. Sensitive actions always require your approval.</p></section>
 <div className="grid"><section className="card"><h2>1. Personal profile</h2>{['full_name','date_of_birth','gender','email','phone'].map(k=><label key={k}>{k.replaceAll('_',' ')}<input value={profile[k]||''} onChange={e=>setProfile({...profile,[k]:e.target.value})}/></label>)}<button onClick={saveProfile} disabled={busy}>Save profile</button></section>
 <section className="card"><h2>2. Document vault</h2><input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={upload}/><div className="list">{docs.map(d=><div className="row" key={d.id}><span>{d.original_filename}</span><small>{d.status}</small><button onClick={()=>extract(d.id)} disabled={busy}>Extract</button></div>)}</div></section>
 <section className="card wide"><h2>3. Fill a website form</h2><label>Website URL<input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://example.com/form"/></label><button onClick={start} disabled={busy||!url}>Open website</button>{session&&<><label>Instruction<textarea value={instruction} onChange={e=>setInstruction(e.target.value)}/></label><button onClick={makePlan} disabled={busy}>Analyze & create plan</button></>}
 {plan&&<div className="plan"><h3>Review detected fields</h3>{(plan.fills||[]).map(x=><div className="fill" key={x.index}><div><b>{x.field}</b><p>{x.value}</p><small>{x.source_type||'profile'} · {x.requires_approval?'Sensitive / approval required':'Safe to fill'}</small></div>{x.requires_approval&&<button onClick={()=>approve(x)} disabled={busy||plan.approvalIds?.[x.index]}> {plan.approvalIds?.[x.index]?'Approved':'Approve'} </button>}</div>)}<button className="primary" onClick={fill} disabled={busy}>Fill approved fields</button>{plan.result&&<pre>{JSON.stringify(plan.result,null,2)}</pre>}</div>}</section></div></main>
 <footer>Formwise never guesses personal data, bypasses CAPTCHA, enters OTP, pays, accepts legal declarations, or clicks final Submit.</footer></div>
}
createRoot(document.getElementById('root')).render(<App/>);
