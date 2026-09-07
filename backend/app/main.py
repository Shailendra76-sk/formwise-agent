from fastapi import FastAPI

app = FastAPI(
    title="Formwise Agent API",
    version="0.1.0",
    description="Secure personal profile and document-vault API foundation.",
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "formwise-api"}
