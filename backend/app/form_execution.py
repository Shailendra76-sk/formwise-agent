from __future__ import annotations
from typing import Any
from app.agent_reasoning import infer_field, _extract_value
from app.approval_engine import SENSITIVE_FIELDS, ApprovalError, consume, create_approval
from app.browser_agent import BrowserSafetyError, fill_control, get_session, inspect_session
from app.form_mapping import map_controls
from app.knowledge_base import load_user_index
from app.storage import PrivateStorage

BLOCKED_TERMS={"captcha","recaptcha","hcaptcha","otp","one time password","payment","pay now","submit","final submission","declaration","i agree"}

def _blocked_page(inspection:dict[str,Any])->list[str]:
    hay=(inspection.get("title","")+" "+inspection.get("url","")+" "+" ".join(str(c.get("text", "")) for c in inspection.get("controls",[]))).lower()
    return sorted(t for t in BLOCKED_TERMS if t in hay)

def _resolve_value(field:str,chunks:list[dict[str,Any]])->dict[str,Any]|None:
    candidates=[]; seen=set()
    for chunk in chunks:
        value=_extract_value(field,str(chunk.get("text","")))
        if value and value not in seen:
            seen.add(value); candidates.append({"field":field,"value":value,"source_type":chunk.get("source_type","unknown"),"source_id":chunk.get("source_id","unknown"),"confidence":float(chunk.get("score",0.0))})
    if len(candidates)==1:return candidates[0]
    if len(candidates)>1:
        exact=[x for x in candidates if x["confidence"]>=0.5]
        if len(exact)==1:return exact[0]
    return None

async def plan_form(user_id:str,session_id:str,instruction:str,storage:PrivateStorage)->dict[str,Any]:
    session=get_session(session_id,user_id); inspection=await inspect_session(session); blocked=_blocked_page(inspection); mappings=map_controls(inspection["controls"])
    index=load_user_index(storage,user_id); requested=infer_field(instruction)
    if not requested:return {"status":"needs_clarification","reason":"Could not identify a supported personal-data field.","inspection":inspection,"mappings":mappings,"proposals":[],"blocked_signals":blocked}
    proposal=_resolve_value(requested,index.get("chunks",[])); proposals=[] if not proposal else [{**proposal,"requires_approval":requested in SENSITIVE_FIELDS}]
    return {"status":"ready" if proposal and not blocked else "blocked" if blocked else "needs_clarification","instruction":instruction,"session_id":session_id,"url":inspection["url"],"title":inspection["title"],"mappings":mappings,"proposals":proposals,"blocked_signals":blocked,"submission_allowed":False,"warnings":["Planning never submits the form.","No value is invented; a stored source is required."]}

async def execute_form(user_id:str,session_id:str,fills:list[dict[str,Any]],storage:PrivateStorage)->dict[str,Any]:
    session=get_session(session_id,user_id); inspection=await inspect_session(session); blocked=_blocked_page(inspection)
    if blocked:return {"status":"blocked","filled":[],"blocked":[{"reason":"safety signal detected","signals":blocked}],"submission_allowed":False}
    mappings=map_controls(inspection["controls"]); results=[]; blocked_items=[]
    for item in fills[:100]:
        try: idx=int(item["index"]); field=str(item["field"]); value=str(item["value"])
        except (KeyError,TypeError,ValueError):blocked_items.append({"reason":"invalid fill request"});continue
        if field in SENSITIVE_FIELDS:
            approval_id=item.get("approval_id")
            if not approval_id:blocked_items.append({"index":idx,"field":field,"reason":"explicit approval is required"});continue
            payload={"index":idx,"field":field,"value":value,"session_id":session_id}
            try:consume(storage,user_id,str(approval_id),"fill_sensitive",session_id,payload)
            except (ApprovalError,KeyError,FileNotFoundError) as exc:blocked_items.append({"index":idx,"field":field,"reason":str(exc)});continue
        if idx<0 or idx>=len(mappings) or mappings[idx].get("field")!=field:blocked_items.append({"index":idx,"field":field,"reason":"mapping is stale or does not match current page; remap required"});continue
        if inspection["controls"][idx].get("value"):blocked_items.append({"index":idx,"field":field,"reason":"existing value detected; silent overwrite is blocked"});continue
        try:
            result=await fill_control(session,idx,value);results.append({**result,"field":field,"provenance":{"source_type":item.get("source_type"),"source_id":item.get("source_id")}})
        except (BrowserSafetyError,ValueError) as exc:blocked_items.append({"index":idx,"field":field,"reason":str(exc)})
    return {"status":"ok" if results else "no_change","filled":results,"blocked":blocked_items,"submission_allowed":False,"review_required":True,"warning":"Formwise never clicks final submit and never bypasses CAPTCHA, OTP, payment or legal declarations."}

def approval_for_sensitive_fill(user_id:str,session_id:str,item:dict[str,Any],storage:PrivateStorage):
    field=str(item.get("field",""))
    if field not in SENSITIVE_FIELDS:raise ApprovalError("approval is only needed for sensitive fields")
    payload={"index":int(item["index"]),"field":field,"value":str(item["value"]),"session_id":session_id}
    return create_approval(storage,user_id,"fill_sensitive",session_id,payload,int(item.get("ttl_seconds",600)))
