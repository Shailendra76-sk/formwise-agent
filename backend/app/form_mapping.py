from __future__ import annotations
import re
from dataclasses import dataclass

FIELD_ALIASES={
"full_name":("full name","fullname","applicant name","candidate name","name","नाम"),
"first_name":("first name","firstname","given name","प्रथम नाम"),
"last_name":("last name","lastname","surname","family name","उपनाम"),
"father_name":("father name","father's name","fathername","पिता का नाम"),
"mother_name":("mother name","mother's name","mothername","माता का नाम"),
"date_of_birth":("date of birth","dob","birth date","birthdate","जन्म तिथि"),
"gender":("gender","sex","लिंग"),
"nationality":("nationality","citizenship","राष्ट्रीयता"),
"category":("category","reservation category","social category","वर्ग","श्रेणी"),
"marital_status":("marital status","marital","वैवाहिक स्थिति"),
"email":("email","email address","e-mail"),
"phone":("phone","mobile","mobile number","telephone","contact number","मोबाइल"),
"aadhaar_number":("aadhaar","aadhaar number","aadhar","uid","uidai"),
"pan_number":("pan","pan number","permanent account number"),
"address":("address","permanent address","current address","mailing address","पता"),
"city":("city","town","शहर"),
"district":("district","जिला"),
"state":("state","province","राज्य"),
"country":("country","देश"),
"postal_code":("pin","pincode","pin code","postal code","zip","zip code"),
"qualification":("qualification","highest qualification","educational qualification","शैक्षिक योग्यता"),
"institution":("institution","school","college","university","board","संस्थान","विद्यालय","महाविद्यालय"),
"roll_number":("roll number","roll no","rollno","रोल नंबर"),
"registration_number":("registration number","registration no","application number","पंजीकरण संख्या"),
"passing_year":("passing year","year of passing","पासिंग ईयर"),
"experience":("experience","work experience","years of experience","अनुभव"),
"designation":("designation","job title","position","पद"),
"photo":("photo","photograph","passport photo","profile photo","फोटो"),
"signature":("signature","sign","signature image","हस्ताक्षर"),
}
SENSITIVE_FIELDS={"aadhaar_number","pan_number","date_of_birth","address","phone","email","gender","father_name","mother_name","nationality","category","marital_status","registration_number","roll_number"}
@dataclass(frozen=True)
class FieldCandidate:
    field:str; score:float; reason:str
def normalize(value:str|None)->str:return re.sub(r"[^a-z0-9]+"," ",(value or "").lower()).strip()
def _label_text(c:dict)->str:return " ".join(str(c.get(k) or "") for k in ("name","id","autocomplete","placeholder","ariaLabel","label","nearbyText","text","type"))
def infer_field(control:dict)->FieldCandidate|None:
    text=normalize(_label_text(control)); typ=normalize(control.get("type")); ac=normalize(control.get("autocomplete")); matches=[]
    for field,aliases in FIELD_ALIASES.items():
        for alias in aliases:
            a=normalize(alias)
            if a and re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])",text): matches.append((len(a),field,alias))
    if matches:
        _,field,alias=max(matches,key=lambda x:x[0]); return FieldCandidate(field,.98,f"matched live form metadata: {alias}")
    if ac in {"name","given-name","family-name"}: return FieldCandidate({"name":"full_name","given-name":"first_name","family-name":"last_name"}[ac],.90,f"autocomplete={ac}")
    if ac=="email" or typ=="email": return FieldCandidate("email",.88,"email control metadata")
    if ac in {"tel","tel-national"} or typ=="tel": return FieldCandidate("phone",.86,"telephone control metadata")
    if typ=="date": return FieldCandidate("date_of_birth",.72,"date input; confirmation required")
    return None
def map_controls(controls:list[dict])->list[dict]:
    out=[]
    for i,c in enumerate(controls):
        x=infer_field(c); out.append({"index":i,"field":x.field if x else None,"confidence":x.score if x else 0.0,"reason":x.reason if x else "no deterministic field match","requires_approval":bool(x and x.field in SENSITIVE_FIELDS)})
    return out
