from __future__ import annotations
import re
from dataclasses import dataclass
TOKEN_RE = re.compile(r"[\w@.+-]+", re.UNICODE)
@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    source_type: str
    source_id: str
    text: str
    metadata: dict

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
def tokenize(text: str) -> list[str]:
    return [x.lower() for x in TOKEN_RE.findall(normalize(text))]
def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    text=normalize(text)
    if not text:return []
    if max_chars<=0 or overlap<0 or overlap>=max_chars:raise ValueError("invalid chunk configuration")
    out=[]; start=0
    while start<len(text):
        end=min(len(text),start+max_chars)
        if end<len(text):
            boundary=text.rfind(" ",start,end)
            if boundary>start+max_chars//2:end=boundary
        out.append(text[start:end])
        if end>=len(text):break
        start=end-overlap
    return out

def rank(query: str,chunks: list[KnowledgeChunk],limit: int=8) -> list[tuple[KnowledgeChunk,float]]:
    q=set(tokenize(query))
    if not q:return []
    scored=[]
    for c in chunks:
        terms=tokenize(c.text)
        if not terms:continue
        hits=sum(terms.count(t) for t in q)
        score=min(1.0,hits/max(len(terms),1)*4)
        if score>0:scored.append((c,score))
    scored.sort(key=lambda x:(-x[1],x[0].chunk_id))
    return scored[:max(0,limit)]
