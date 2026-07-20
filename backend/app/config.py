"""Environment loading, in one place.

Importing this module loads backend/.env into the process environment. Python
caches module execution, so it happens exactly once no matter how many modules
import it.

This exists because .env loading used to live inside llm.py. Anything that
imported the enrichment clients WITHOUT importing llm — the client test harness,
for instance — got a bare environment, so a correctly configured API key read as
"not set" and the source silently reported itself unavailable. A misconfiguration
that looks identical to a missing key is the worst kind, so the load now belongs
to a module every consumer can depend on.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Resolve .env from the backend root, so it is found whether the process was
# launched via uvicorn, a script, or pytest from some other directory.
load_dotenv(BACKEND_ROOT / ".env")
