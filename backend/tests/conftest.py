"""
Test setup. Environment must be configured before `app` is imported, because
settings are read once at import time.
"""
import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="tnr-tests-"))
os.environ.update({
    "ANTHROPIC_API_KEY": "test-key",
    "OPENAI_API_KEY": "",
    "DATABASE_URL": "",
    "DOWNLOADS_DIR": str(_TMP / "downloads"),
    "HISTORY_DB_PATH": str(_TMP / "history.db"),
    "RATE_LIMIT_GENERATIONS_PER_HOUR": "1000",
    "RATE_LIMIT_AI_CALLS_PER_HOUR": "1000",
})

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
