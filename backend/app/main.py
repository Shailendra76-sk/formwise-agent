from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.agent_routes import router as agent_router
from app.browser_agent import close_all_sessions
from app.browser_routes import router as browser_router
from app.form_mapping_routes import router as form_mapping_router
from app.knowledge_routes import router as knowledge_router
from app.routes import router
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_all_sessions()
app=FastAPI(title='Formwise Agent API',version='0.1.0',description='Secure profile, document-vault, knowledge, agent planning, controlled browser and form mapping API.',lifespan=lifespan)
app.include_router(router); app.include_router(knowledge_router); app.include_router(agent_router); app.include_router(browser_router); app.include_router(form_mapping_router)
@app.get('/health',tags=['system'])
async def health()->dict[str,str]: return {'status':'ok','service':'formwise-api'}
