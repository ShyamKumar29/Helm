# Phase B0 — Bootstrap and the Frozen Shell

**Window:** H+0 → H+1 (the first hour; the first ten minutes of it are the most important)
**Blocks:** everyone

---

## 1. Goal

Two outcomes. First, make the repository safe to clone: `.gitignore` and `docker-compose.yml`
land on `main` **before anyone else's first commit**. Second, stand up a FastAPI server that
answers every route in `FINAL.md` section 10 with the correct shape, read straight from
`contracts/fixtures/`. No database, no engine, no logic.

By the end of this hour Person C can point the frontend at `http://localhost:8000` and get
valid data from every endpoint. That is worth more than any real logic you could have written
in the same hour.

## 2. Files

Create:

```
.gitignore                       # first commit of the whole repo
docker-compose.yml
.env.example
api/__init__.py
api/requirements.txt
api/main.py                      # WRITE ONCE, THEN FROZEN
api/config.py                    # env loading, one place
api/errors.py                    # the frozen error envelope
api/fixtures.py                  # fixture loader used by every stub
api/routers/__init__.py
api/routers/state.py
api/routers/sim.py
api/routers/decisions.py
api/routers/events.py
api/routers/compare.py
api/services/__init__.py
scripts/reset.sh                 # stub for now
```

## 3. Build steps

### Step 1 — `.gitignore`, first, before anything

Exactly the block in `FINAL.md` section 7. Commit it alone:

```bash
git add .gitignore
git commit -m "chore: gitignore before first code commit"
git push origin main
```

Then tell the room: *"gitignore is on main, everybody clone now."*

### Step 2 — `docker-compose.yml`

Exactly the block in `FINAL.md` section 13. Postgres only. The API and the frontend run
natively; container rebuilds during a hackathon cost more than they save.

```bash
docker compose up -d db
docker compose ps          # expect healthy
```

### Step 3 — `.env.example` and `api/config.py`

`.env.example` is the block in `FINAL.md` section 18. `config.py` reads it once:

```python
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
```

**Nothing else in `api/` calls `os.getenv`.** One place, one time.

### Step 4 — `api/errors.py`, the frozen envelope

```python
# api/errors.py
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

class HelmError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, detail: dict | None = None):
        self.code, self.message, self.status, self.detail = code, message, status, detail or {}

def _envelope(code: str, message: str, detail: dict, status: int) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": {"code": code, "message": message, "detail": detail}})

def register(app):
    @app.exception_handler(HelmError)
    async def _helm(_: Request, exc: HelmError):
        return _envelope(exc.code, exc.message, exc.detail, exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return _envelope("VALIDATION", "Request body failed validation",
                         {"errors": exc.errors()}, 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 409: "CONFLICT", 400: "BAD_REQUEST"}.get(exc.status_code, "HTTP_ERROR")
        return _envelope(code, str(exc.detail), {}, exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return _envelope("INTERNAL", "Unexpected server error", {"type": type(exc).__name__}, 500)
```

That last handler is why the frontend never sees an HTML error page. Register it at H+1 and
you are covered for the rest of the night.

### Step 5 — `api/fixtures.py`

```python
# api/fixtures.py
import json, pathlib
from functools import lru_cache

_DIR = pathlib.Path(__file__).resolve().parents[1] / "contracts" / "fixtures"

@lru_cache(maxsize=None)
def load(name: str):
    return json.loads((_DIR / name).read_text(encoding="utf-8"))
```

If Shyam has not written the fixtures yet, every route 500s with a clean envelope, which is
fine — say so out loud and keep building. They land inside the same hour.

### Step 6 — `api/main.py`, written once, then frozen

```python
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
```

**Do not open this file again.** Every future route lives in a router module.

### Step 7 — stub every route from fixtures

Each router returns the fixture with the right shape. Example:

```python
# api/routers/state.py
from fastapi import APIRouter, Query
from api import fixtures

router = APIRouter(tags=["state"])

@router.get("/state")
def get_state(policy: str = Query("AGENT")):
    return fixtures.load("state.sample.json")

@router.get("/forecast")
def get_forecast(horizon: int = Query(90), policy: str = Query("AGENT")):
    return fixtures.load("forecast.sample.json")
```

Do the same for `sim`, `decisions`, `events`, `compare`. **Every route in section 10 exists
and answers.** Write-shaped routes (`/sim/reset`, `/decide`, `POST /events`, `/weights`,
`/execute/{id}`) return the fixture-derived shape they will eventually return for real.

### Step 8 — CORS check with Person C

Have Person C hit `http://localhost:8000/api/state` from the Vite dev server before you move
on. Twenty seconds now, twenty minutes saved later.

## 4. Definition of done

- [ ] `.gitignore` is the first commit on `main`, pushed, everyone has cloned after it
- [ ] `docker compose up -d db` reports healthy
- [ ] `.env.example` committed; a local `.env` exists and is ignored by git
- [ ] `uvicorn api.main:app --reload --port 8000` boots with zero tracebacks
- [ ] `main.py` is complete and declared frozen out loud
- [ ] All five routers exist and every route in `FINAL.md` section 10 responds
- [ ] Error envelope proven: an intentionally bad request returns `{"error": {...}}`, not HTML
- [ ] Person C has fetched a route from the browser successfully (CORS proven)

## 5. Verify

```bash
uvicorn api.main:app --port 8000 &

curl -s localhost:8000/api/health
curl -s localhost:8000/api/state    | head -c 200
curl -s localhost:8000/api/forecast | head -c 200
curl -s "localhost:8000/api/decisions?policy=AGENT" | head -c 200
curl -s localhost:8000/api/events   | head -c 200
curl -s localhost:8000/api/compare  | head -c 200
curl -s localhost:8000/api/sim/status

# error envelope
curl -s -X POST localhost:8000/api/sim/step -H 'content-type: application/json' -d '{"days":"nope"}'
# expect: {"error":{"code":"VALIDATION",...}}
```

The last one is the important test. If it returns a FastAPI default validation dump instead of
the envelope, `errors.register(app)` is not wired.
