from .retrieval_engine import retrieve, split_chunks


def search_text(query: str, text: str, limit: int = 8):
    chunks = split_chunks(text)
    return retrieve(query, chunks, limit)
