# api/fixtures.py
import json, pathlib
from functools import lru_cache

_DIR = pathlib.Path(__file__).resolve().parents[1] / "contracts" / "fixtures"


@lru_cache(maxsize=None)
def load(name: str):
    return json.loads((_DIR / name).read_text(encoding="utf-8"))
