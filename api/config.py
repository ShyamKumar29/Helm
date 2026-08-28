# api/config.py
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL          = os.getenv("DATABASE_URL", "postgresql+psycopg://helm:helm@localhost:5432/helm")
SIM_SEED              = int(os.getenv("SIM_SEED", "42"))
SIM_START_DATE        = os.getenv("SIM_START_DATE", "2026-03-01")
MATERIALITY_THRESHOLD = float(os.getenv("MATERIALITY_THRESHOLD", "0.15"))
SOLVER_TIMEOUT_MS     = int(os.getenv("SOLVER_TIMEOUT_MS", "2000"))
CORS_ORIGINS          = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
HORIZON_DAYS          = int(os.getenv("HORIZON_DAYS", "90"))
EXPLAINER_MODE        = os.getenv("EXPLAINER_MODE", "template")
API_SELF_BASE_URL     = os.getenv("API_SELF_BASE_URL", "http://127.0.0.1:8000/api")
