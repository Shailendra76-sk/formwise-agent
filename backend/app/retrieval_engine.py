import re

def tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))

def split_chunks(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("invalid chunk settings")
    text = re.sub(r"\s+", " ", text).strip()
    result=[]; start=0
    while start < len(text):
        end=min(len(text),start+size); result.append(text[start:end])
        if end == len(text): break
        start=end-overlap
    return result

def retrieve(query: str, chunks: list[str], limit: int = 8) -> list[tuple[int,float,str]]:
    q=tokens(query)
    if not q:return []
    scored=[]
    for i,chunk in enumerate(chunks):
        words=tokens(chunk)
        if not words:continue
        score=len(q & words)/len(q)
        if score:scored.append((i,score,chunk))
    return sorted(scored,key=lambda x:(-x[1],x[0]))[:limit]
