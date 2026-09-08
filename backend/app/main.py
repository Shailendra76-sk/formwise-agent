from fastapi import FastAPI

from app.routes import router
from app.knowledge_routes import router as knowledge_router

app = FastAPI(
    title="Formwise Agent API",
    version="0.1.0",
    description="Secure profile and document-vault API foundation.",
)

app.include_router(router)
app.include_router(knowledge_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "formwise-api"}
