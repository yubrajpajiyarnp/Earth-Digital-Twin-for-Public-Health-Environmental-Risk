from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db.database import init_db
from app.models.risk.knowledge_graph import seed_graph_if_empty
from app.models.simulation.disaster_ml import start_background_training

app = FastAPI(title="Nepal Hydro-Geological Disaster Digital Twin API")
init_db()
seed_graph_if_empty()
# Loads the persisted model, or (re)trains it in a background thread if missing or stale —
# the API starts serving immediately either way.
start_background_training()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
