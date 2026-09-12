from __future__ import annotations
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.agent_reasoning import _extract_value
from app.approval_engine import SENSITIVE_FIELDS, ApprovalError, consume, create_approval
from app.browser_agent import BrowserSafetyError, get_session, inspect_session, upload_control
from app.db_models import DocumentRecord
from app.form_mapping import map_controls
from app.knowledge_base import load_user_index
from app.storage import PrivateStorage

BLOCKED_PAGE_TERMS={"payment","pay now","final submission","legal declaration","i agree","anti-bot","anti bot","bot verification"}

def _control_text(control:dict[str,Any])->str:return " ".join(str(control.get(k, "")) for k in ("text","ariaLabel","placeholder","name","id","autocomplete")).lower()
def _page_signals(inspection:dict[str,Any])->dict[str,list[str]]:
    blocked=set();human=set()
    for control in inspection.get("controls",[]):
        text=_control_text(control);typ=str(control.get("type","")).lower();value=str(control.get("value") or "")
        if any(term in text for term in ("captcha","recaptcha","hcaptcha")) and not value:human.add("captcha")
        if ("otp" in text or "one time password" in text or control.get("autocomplete") in {"one-time-code","one-time-password"}) and not value:human.add("otp")
        if "payment" in text or "pay now" in text:blocked.add("payment")
        if "declaration" in text or "i agree" in text:blocked.add("legal declaration")
        if "anti-bot" in text or "anti bot" in text or "bot verification" in text:blocked.add("anti-bot")
        if typ=="submit" and any(term in text for term in ("final submission","final submit","submit application","confirm and submit","complete application")):blocked.add("final submission")
    page_text=(inspection.get("title","")+" "+inspection.get("url","")).lower()
    if "payment" in page_text or "pay now" in page_text:blocked.add("payment")
    if "anti-bot" in page_text or "anti bot" in page_text or "bot verification" in page_text:blocked.add("anti-bot")
    return {"blocked":sorted(blocked),"human":sorted(human)}
def _blocked_page(inspection:dict[str,Any])->list[str]:return _page_signals(inspection)["blocked"]
def _resolve_value(field:str,chunks:list[dict[str,Any]])->dict[str,Any]|None:
    candidates=[];seen=set()
    for chunk in chunks:
        value=_extract_value(field,str(chunk.get("text","")))
        if value and value not in seen:
            seen.add(value);candidates.append({"field":field,"value":value,"source_type":chunk.get("source_type","unknown"),"source_id":chunk.get("source_id","unknown"),"confidence":float(chunk.get("score",0.0))})
    if len(candidates)==1:return candidates[0]
    if len(candidates)>1:
        exact=[x for x in candidates if x["confidence"]>=0.5]
        if len(exact)==1:return exact[0]
    return None

def _document_proposal(field:str,db:Session,user_id:str)->dict[str,Any]|None:
    if field not in {"photo","signature"}:return None
    rows=db.scalars(select(DocumentRecord).where(DocumentRecord.user_id==user_id,DocumentRecord.status!="deleted")).all()
    matches=[r for r in rows if field=="photo" and ("photo" in r.original_filename.lower() or "passport" in r.original_filename.lower()) or field=="signature" and ("signature" in r.original_filename.lower() or "sign" in r.original_filename.lower())]
    if len(matches)==1:
        r=matches[0];return {"field":field,"value":r.original_filename,"source_type":"document","source_id":r.id,"document_id":r.id,"confidence":1.0}
    return None

async def plan_form(user_id:str,session_id:str,instruction:str,storage:PrivateStorage,db:Session|None=None)->dict[str,Any]:
    session=get_session(session_id,user_id);inspection=await inspect_session(session);signals=_page_signals(inspection);mappings=map_controls(inspection["controls"]);index=load_user_index(storage,user_id);chunks=index.get("chunks",[]);proposals=[]
    for mapping in mappings:
        field=mapping.get("field")
        if not field or mapping.get("confidence",0)<0.70 or inspection["controls"][mapping["index"]].get("disabled"):continue
        value=_document_proposal(field,db,user_id) if db else None
        value=value or _resolve_value(field,chunks)
        if value:proposals.append({**value,"index":mapping["index"],"requires_approval":field in SENSITIVE_FIELDS,"reason":mapping.get("reason")})
    fills=[dict(item) for item in proposals]
    status="blocked" if signals["blocked"] else ("ready" if proposals else "needs_clarification")
    return {"status":status,"instruction":instruction,"session_id":session_id,"url":inspection["url"],"title":inspection["title"],"mappings":mappings,"proposals":proposals,"fills":fills,"blocked_signals":signals["blocked"],"human_required":signals["human"],"submission_allowed":False,"warnings":["Only deterministic mapped fields with stored values are proposed.","No value is invented.","Sensitive fields require explicit approval.","CAPTCHA and OTP are human gates; they are never read or solved by Formwise.","Payment, anti-bot bypass, legal declarations and final submission are never automated."]}

async def execute_form(user_id:str,session_id:str,fills:list[dict[str,Any]],storage:PrivateStorage,db:Session|None=None)->dict[str,Any]:
    session=get_session(session_id,user_id);inspection=await inspect_session(session);blocked=_blocked_page(inspection)
    if blocked:return {"status":"blocked","filled":[],"blocked":[{"reason":"safety signal detected","signals":blocked}],"submission_allowed":False}
    mappings=map_controls(inspection["controls"]);results=[];blocked_items=[]
    for item in fills[:100]:
        try:idx=int(item["index"]);field=str(item["field"]);value=str(item["value"])
        except (KeyError,TypeError,ValueError):blocked_items.append({"reason":"invalid fill request"});continue
        if field in SENSITIVE_FIELDS:
            approval_id=item.get("approval_id")
            if not approval_id:blocked_items.append({"index":idx,"field":field,"reason":"explicit approval is required"});continue
            payload={"index":idx,"field":field,"value":value,"session_id":session_id}
            try:consume(storage,user_id,str(approval_id),"fill_sensitive",session_id,payload)
            except (ApprovalError,KeyError,FileNotFoundError) as exc:blocked_items.append({"index":idx,"field":field,"reason":str(exc)});continue
        if idx<0 or idx>=len(mappings) or mappings[idx].get("field")!=field:blocked_items.append({"index":idx,"field":field,"reason":"mapping is stale; remap required"});continue
        if inspection["controls"][idx].get("value") and field not in {"photo","signature"}:blocked_items.append({"index":idx,"field":field,"reason":"existing value detected; silent overwrite is blocked"});continue
        try:
            if field in {"photo","signature"}:
                if not db: raise BrowserSafetyError("document upload requires database context")
                doc_id=str(item.get("document_id") or item.get("source_id") or "")
                row=db.get(DocumentRecord,doc_id)
                if not row or row.user_id!=user_id or row.status=="deleted":raise BrowserSafetyError("document is not available for this user")
                result=await upload_control(session,idx,str(storage.key_path(user_id,row.storage_key)))
            else:
                from app.browser_agent import fill_control
                result=await fill_control(session,idx,value)
            results.append({**result,"field":field,"provenance":{"source_type":item.get("source_type"),"source_id":item.get("source_id")}})
        except (BrowserSafetyError,ValueError) as exc:blocked_items.append({"index":idx,"field":field,"reason":str(exc)})
    signals=_page_signals(await inspect_session(session))
    return {"status":"ok" if results else "no_change","filled":results,"blocked":blocked_items,"human_required":signals["human"],"submission_allowed":False,"review_required":True,"warning":"Review the page after filling. Formwise never clicks final submit and never bypasses CAPTCHA, OTP, payment or legal declarations."}

def approval_for_sensitive_fill(user_id:str,session_id:str,item:dict[str,Any],storage:PrivateStorage):
    field=str(item.get("field",""))
    if field not in SENSITIVE_FIELDS:raise ApprovalError("approval is only needed for sensitive fields")
    payload={"index":int(item["index"]),"field":field,"value":str(item["value"]),"session_id":session_id}
    return create_approval(storage,user_id,"fill_sensitive",session_id,payload,int(item.get("ttl_seconds",600)))
