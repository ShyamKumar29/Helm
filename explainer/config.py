# explainer/config.py — own env config, independent of api/config.py (FINAL.md line 1705:
# "explainer/ may import from engine/ and contracts/, but must never import from api/").
import os

from dotenv import load_dotenv

load_dotenv()

# The API this package calls itself, over HTTP, to fetch a decision by id — never a Python
# import of api/ (see module docstring above). Same convention as api/config.py's own
# API_SELF_BASE_URL for its self-calls into this package.
API_BASE_URL = os.getenv("HELM_API_BASE_URL", "http://127.0.0.1:8000/api")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_TIMEOUT_S = float(os.getenv("GROQ_TIMEOUT_S", "8.0"))
