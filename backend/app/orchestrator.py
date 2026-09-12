from __future__ import annotations
import re,time,uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.approval_engine import consume,create_approval
from app.browser_agent import fill_control,get_session,inspect_session,screenshot_session
from app.db_models import AuditLogRecord,DocumentRecord,ProfileRecord
from app.form_execution import execute_form,plan_form
from app.research import research_exam
from app.storage import PrivateStorage
WORKFLOW_KEY="workflows/{workflow_id}.json"
def _key(workflow_id:str)->str:return WORKFLOW_KEY.format(workflow_id=workflow_id)
def _save(storage:PrivateStorage,user_id:str,workflow:dict[str,Any])->None:storage.save_json(user_id,_key(workflow["workflow_id"]),workflow)
def load_workflow(storage:PrivateStorage,user_id:str,workflow_id:str)->dict[str,Any]:return storage.read_json(user_id,_key(workflow_id))
def _audit(db:Session,user_id:str,action:str,workflow_id:str)->None:db.add(AuditLogRecord(user_id=user_id,action=action,resource_type="workflow",resource_id=workflow_id));db.commit()
def _doc_kind(filename:str)->str:
    name=filename.lower()
    if any(x in name for x in ("10th","matric","class10","highschool")):return "education_10th"
    if any(x in name for x in ("12th","inter","class12","intermediate")):return "education_12th"
    if any(x in name for x in ("aadhaar","aadhar","uid")):return "identity"
    if "pan" in name:return "pan"
    if any(x in name for x in ("caste","sc","st","obc","ews")):return "category_certificate"
    if any(x in name for x in ("photo","passport")):return "photo"
    if any(x in name for x in ("signature","sign")):return "signature"
    return "other"
def _document_checklist(db:Session,user_id:str,storage:PrivateStorage)->dict[str,Any]:
    rows=db.scalars(select(DocumentRecord).where(DocumentRecord.user_id==user_id,DocumentRecord.status!="deleted")).all();kinds=set();extracted=[]
    for row in rows:
        kind=_doc_kind(row.original_filename);kinds.add(kind)
        try:
            data=storage.read_json(user_id,f"{row.storage_key}.extraction.json");fields=data.get("fields",[]);extracted.append({"document_id":row.id,"filename":row.original_filename,"status":data.get("status"),"fields":[f.get("name") for f in fields if f.get("name")],"engine":data.get("engine")})
        except FileNotFoundError:extracted.append({"document_id":row.id,"filename":row.original_filename,"status":"not_extracted","fields":[]})
    profile=db.get(ProfileRecord,user_id);required=[{"key":"identity","label":"Identity/address proof","required":True},{"key":"education_12th","label":"Class 12 / equivalent qualification proof","required":True},{"key":"photo","label":"Recent photograph","required":True},{"key":"signature","label":"Signature image","required":True}]
    missing=[x for x in required if x["key"] not in kinds];not_extracted=[x for x in extracted if x["status"]=="not_extracted"];profile_missing=[field for field in ("full_name","date_of_birth","gender","email","phone") if not getattr(profile,field,None)]
    return {"documents":[{"key":x["key"],"label":x["label"],"present":x["key"] not in {m["key"] for m in missing}} for x in required],"extracted_documents":extracted,"missing_documents":missing,"documents_needing_ocr":not_extracted,"missing_profile_fields":profile_missing,"ready":not missing and not not_extracted and not profile_missing}
def _otp_control(inspection:dict[str,Any])->int|None:
    for c in inspection.get("controls",[]):
        hay=" ".join(str(c.get(k) or "") for k in ("name","id","placeholder","ariaLabel","autocomplete","text")).lower()
        if "otp" in hay or "one time password" in hay or c.get("autocomplete") in {"one-time-code","one-time-password"}:return int(c["index"])
    return None
def _final_submit_control(inspection:dict[str,Any])->int|None:
    candidates=[]
    for c in inspection.get("controls",[]):
        typ=str(c.get("type") or "").lower()
        if typ not in {"submit","button"}:continue
        text=" ".join(str(c.get(k) or "") for k in ("text","ariaLabel","name","id")).lower()
        if any(x in text for x in ("submit application","final submit","confirm and submit","submit form","complete application")) or (typ=="submit" and text.strip() in {"submit","submit form"}):candidates.append(int(c["index"]))
    return candidates[0] if len(candidates)==1 else None
async def start_workflow(db:Session,storage:PrivateStorage,user_id:str,instruction:str)->dict[str,Any]:
    match=re.search(r"(?:ssc\s*)?(chsl|combined higher secondary).*?(20\d{2})",instruction.lower()) or re.search(r"chsl.*?(20\d{2})",instruction.lower());exam="SSC CHSL" if "chsl" in instruction.lower() else instruction.strip()[:120];year=int(match.group(2) if match and match.lastindex and match.lastindex>=2 else (match.group(1) if match else time.gmtime().tm_year));research=await research_exam(exam,year);workflow={"workflow_id":uuid.uuid4().hex,"user_id":user_id,"instruction":instruction,"exam":exam,"year":year,"state":"research_ready","created_at":time.time(),"research":research,"document_check":None,"session_id":None,"last_screenshot_key":None,"history":[]};_save(storage,user_id,workflow);_audit(db,user_id,"workflow.research_completed",workflow["workflow_id"]);return workflow
def confirm_research(db:Session,storage:PrivateStorage,user_id:str,workflow_id:str,confirmed:bool)->dict[str,Any]:
    workflow=load_workflow(storage,user_id,workflow_id)
    if workflow["state"] not in {"research_ready","documents_missing"}:raise ValueError("workflow is not awaiting document/research confirmation")
    if not confirmed:workflow["state"]="cancelled";_save(storage,user_id,workflow);_audit(db,user_id,"workflow.cancelled",workflow_id);return workflow
    check=_document_checklist(db,user_id,storage);workflow["document_check"]=check;workflow["state"]="documents_ready" if check["ready"] else "documents_missing";workflow["history"].append({"event":"checklist_confirmed","at":time.time()});_save(storage,user_id,workflow);_audit(db,user_id,"workflow.document_check_completed",workflow_id);return workflow
async def open_application(db:Session,storage:PrivateStorage,user_id:str,workflow_id:str)->dict[str,Any]:
    workflow=load_workflow(storage,user_id,workflow_id)
    if workflow["state"]!="documents_ready":raise ValueError("complete the missing profile/document checklist first")
    from app.browser_agent import create_session
    session=await create_session(user_id,workflow["research"].get("apply_url") or "https://ssc.gov.in/");inspection=await inspect_session(session);workflow["session_id"]=session.session_id;workflow["state"]="browser_ready";workflow["history"].append({"event":"application_opened","url":inspection["url"],"at":time.time()});_save(storage,user_id,workflow);_audit(db,user_id,"workflow.browser_opened",workflow_id);return {**workflow,"inspection":inspection}
async def submit_otp(db:Session,storage:PrivateStorage,user_id:str,workflow_id:str,otp:str)->dict[str,Any]:
    workflow=load_workflow(storage,user_id,workflow_id);session_id=workflow.get("session_id")
    if not session_id:raise ValueError("browser session not started")
    if workflow["state"] not in {"browser_ready","otp_required"}:raise ValueError("workflow is not awaiting OTP")
    if not re.fullmatch(r"\d{4,8}",otp):raise ValueError("OTP must be 4-8 digits")
    session=get_session(session_id,user_id);inspection=await inspect_session(session);idx=_otp_control(inspection)
    if idx is None:raise ValueError("OTP field was not detected; no OTP was entered")
    await fill_control(session,idx,otp);screenshot=await screenshot_session(session);key=f"workflow/{workflow_id}/otp-{uuid.uuid4().hex}.png";storage.save(user_id,key,screenshot);workflow["state"]="browser_ready";workflow["last_screenshot_key"]=key;workflow["history"].append({"event":"otp_entered_by_user","at":time.time()});_save(storage,user_id,workflow);_audit(db,user_id,"workflow.otp_entered",workflow_id);return {**workflow,"inspection":await inspect_session(session),"otp_field_index":idx}
async def prepare_form(db:Session,storage:PrivateStorage,user_id:str,workflow_id:str)->dict[str,Any]:
    workflow=load_workflow(storage,user_id,workflow_id);session_id=workflow.get("session_id")
    if not session_id:raise ValueError("browser session not started")
    inspection=await inspect_session(get_session(session_id,user_id))
    if _otp_control(inspection) is not None:workflow["state"]="otp_required";workflow["plan"]={"status":"otp_required","fills":[],"blocked_signals":[]};_save(storage,user_id,workflow);return workflow
    plan=await plan_form(user_id,session_id,workflow["instruction"],storage);workflow["state"]="form_review" if plan["status"]=="ready" else plan["status"];workflow["plan"]=plan;workflow["history"].append({"event":"form_plan_created","at":time.time()});_save(storage,user_id,workflow);_audit(db,user_id,"workflow.form_plan_created",workflow_id);return {**workflow,"plan":plan}
async def fill_form(db:Session,storage:PrivateStorage,user_id:str,workflow_id:str,fills:list[dict[str,Any]])->dict[str,Any]:
    workflow=load_workflow(storage,user_id,workflow_id);session_id=workflow["session_id"];all_results=[];all_blocked=[];screens=[]
    for item in fills:
        result=await execute_form(user_id,session_id,[item],storage);all_results.extend(result.get("filled",[]));all_blocked.extend(result.get("blocked",[]))
        try:shot=await screenshot_session(get_session(session_id,user_id));key=f"workflow/{workflow_id}/step-{len(screens)+1}-{uuid.uuid4().hex}.png";storage.save(user_id,key,shot);screens.append(key)
        except Exception:pass
    result={"status":"ok" if all_results else "no_change","filled":all_results,"blocked":all_blocked,"submission_allowed":False,"review_required":True,"screenshots":screens};workflow["state"]="final_review" if all_results else workflow.get("state");workflow["last_screenshot_key"]=screens[-1] if screens else workflow.get("last_screenshot_key");workflow["result"]=result;workflow["history"].append({"event":"form_filled","filled":len(all_results),"screenshots":len(screens),"at":time.time()});_save(storage,user_id,workflow);_audit(db,user_id,"workflow.form_filled",workflow_id);return {**workflow,"result":result}
def request_final_approval(storage:PrivateStorage,user_id:str,workflow_id:str)->dict[str,Any]:
    workflow=load_workflow(storage,user_id,workflow_id)
    if workflow.get("state")!="final_review":raise ValueError("workflow is not ready for final review")
    payload={"workflow_id":workflow_id,"session_id":workflow["session_id"],"screenshot_key":workflow.get("last_screenshot_key")};approval=create_approval(storage,user_id,"final_submit",workflow["session_id"],payload,600);return {"approval_id":approval.approval_id,"expires_at":approval.expires_at,"payload":payload}
async def final_submit(db:Session,storage:PrivateStorage,user_id:str,workflow_id:str,approval_id:str)->dict[str,Any]:
    workflow=load_workflow(storage,user_id,workflow_id)
    if workflow.get("state")!="final_review":raise ValueError("final review is required before submission")
    payload={"workflow_id":workflow_id,"session_id":workflow["session_id"],"screenshot_key":workflow.get("last_screenshot_key")};consume(storage,user_id,approval_id,"final_submit",workflow["session_id"],payload);session=get_session(workflow["session_id"],user_id);inspection=await inspect_session(session);idx=_final_submit_control(inspection)
    if idx is None:raise ValueError("unique final submit control was not detected; nothing was submitted")
    await session.page.locator('input, textarea, select, button').nth(idx).click();await session.page.wait_for_load_state("domcontentloaded");screenshot=await screenshot_session(session);key=f"workflow/{workflow_id}/submitted-{uuid.uuid4().hex}.png";storage.save(user_id,key,screenshot);workflow["state"]="submitted";workflow["last_screenshot_key"]=key;workflow["history"].append({"event":"final_submission","at":time.time()});_save(storage,user_id,workflow);_audit(db,user_id,"workflow.final_submitted",workflow_id);return {**workflow,"submitted":True,"screenshot_key":key,"url":session.page.url}
