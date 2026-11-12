"""Portable runtime settings for the Flask application.

Process environment variables take precedence over the repository-root .env.
Runtime files are kept outside the source tree under TJT_DATA_DIR.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env", override=False)

DATA_DIR = Path(os.getenv("TJT_DATA_DIR") or REPO_ROOT / "var").expanduser()
if not DATA_DIR.is_absolute():
    DATA_DIR = REPO_ROOT / DATA_DIR
DATA_DIR = DATA_DIR.resolve()

INPUT_DIR = DATA_DIR / "inputs"
OUTPUT_DIR = DATA_DIR / "outputs"
PATIENT_INFO_DIR = DATA_DIR / "patient_info"
REPORT_DIR = DATA_DIR / "reports"
ANNOTATED_DIR = DATA_DIR / "annotated_images"
HTML_REPORT_DIR = DATA_DIR / "html_reports"

for directory in (
    INPUT_DIR,
    OUTPUT_DIR,
    PATIENT_INFO_DIR,
    REPORT_DIR,
    ANNOTATED_DIR,
    HTML_REPORT_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)

ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "").strip()
ROBOFLOW_API_URL = os.getenv("ROBOFLOW_API_URL") or "https://detect.roboflow.com"
TONGJI_AGENT_API_KEY = os.getenv("TONGJI_AGENT_API_KEY", "").strip()
TONGJI_AGENT_BASE_URL = (
    os.getenv("TONGJI_AGENT_BASE_URL") or "https://agent.tongji.edu.cn/api/proxy"
).rstrip("/")
TONGJI_AGENT_USER_ID = os.getenv("TONGJI_AGENT_USER_ID") or "tj-toothai"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
QRCODE_API_URL = (
    os.getenv("QRCODE_API_URL") or "http://127.0.0.1:16666/v1/create-qr-code/"
)

FONT_PATH = os.getenv("TJT_FONT_PATH", "").strip()
if FONT_PATH:
    font_path = Path(FONT_PATH).expanduser()
    if not font_path.is_absolute():
        font_path = REPO_ROOT / font_path
    FONT_PATH = str(font_path)

HOST = os.getenv("TJT_HOST") or "127.0.0.1"
PORT = int(os.getenv("TJT_PORT") or "5000")
