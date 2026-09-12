
# Universal target-discovery override. The implementation above remains as a compatibility
# path, while this final definition is the public workflow entry point used by routes.
async def start_workflow(db:Session,storage:PrivateStorage,user_id:str,instruction:str,provided_url:str|None=None)->dict[str,Any]:
    research=await discover_target(instruction,provided_url)
    # Normalize the universal research result to the fields consumed by the existing workflow.
    if research.get("application_form_url"):
        research["apply_url"]=research["application_form_url"]
    workflow={"workflow_id":uuid.uuid4().hex,"user_id":user_id,"instruction":instruction,"state":"awaiting_url" if research.get("needs_user_url") else "research_ready","created_at":time.time(),"research":research,"document_check":None,"session_id":None,"last_screenshot_key":None,"history":[]}
    _save(storage,user_id,workflow);_audit(db,user_id,"workflow.research_completed",workflow["workflow_id"]);return workflow

async def set_target_url(db:Session,storage:PrivateStorage,user_id:str,workflow_id:str,url:str)->dict[str,Any]:
    workflow=load_workflow(storage,user_id,workflow_id)
    research=await discover_target(workflow["instruction"],url)
    if research.get("application_form_url"): research["apply_url"]=research["application_form_url"]
    workflow["research"]=research
    workflow["state"]="research_ready" if research.get("status") in {"ready","needs_verification"} else "awaiting_url"
    workflow["history"].append({"event":"target_url_provided","at":time.time()})
    _save(storage,user_id,workflow);_audit(db,user_id,"workflow.target_url_provided",workflow_id);return workflow
