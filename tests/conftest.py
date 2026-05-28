import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SERVER_DIR = REPO_ROOT / "environment" / "frontend_server"

if str(FRONTEND_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_SERVER_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "frontend_server.settings.local")

import django  # noqa: E402

django.setup()
