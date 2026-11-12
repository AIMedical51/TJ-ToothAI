"""WSGI entry point; configure the Python environment in the process manager."""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from app import app as application
