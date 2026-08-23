from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db.database import init_db
from app.services.knowledge_graph.graph import seed_graph_if_empty

app = FastAPI(title="Earth Digital Twin API")
init_db()
seed_graph_if_empty()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
