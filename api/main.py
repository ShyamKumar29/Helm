# api/main.py — written once at H+1, then FROZEN
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import config, errors

app = FastAPI(title="HELM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

errors.register(app)

from api.routers import state, sim, decisions, events, compare
app.include_router(state.router,     prefix="/api")
app.include_router(sim.router,       prefix="/api")
app.include_router(decisions.router, prefix="/api")
app.include_router(events.router,    prefix="/api")
app.include_router(compare.router,   prefix="/api")

try:
    from explainer.router import router as explainer_router
    app.include_router(explainer_router, prefix="/api")
except Exception as e:
    logging.getLogger(__name__).warning("explainer not mounted: %s", e)


@app.get("/api/health")
def health():
    return {"ok": True}
