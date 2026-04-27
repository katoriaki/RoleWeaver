import os
import sys
from pathlib import Path

from dotenv import load_dotenv


LINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = LINE_DIR.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_line_env() -> None:
    load_dotenv(LINE_DIR / ".env", override=False)
    load_dotenv(REPO_ROOT / ".env", override=False)


def require_line_env() -> list[str]:
    missing = []
    for name in ("LINE_CHANNEL_SECRET", "LINE_CHANNEL_ACCESS_TOKEN"):
        if not os.getenv(name):
            missing.append(name)
    return missing


def main() -> int:
    load_line_env()
    missing = require_line_env()
    if missing:
        print("[RoleWeaver LINE] Missing required settings:")
        for name in missing:
            print(f"  - {name}")
        print()
        print("Create line\\.env from line\\.env.example and fill your LINE channel values.")
        return 2

    try:
        import uvicorn
    except ImportError:
        print("[RoleWeaver LINE] Missing dependency: uvicorn")
        print("Run: python -m pip install -r line\\requirements.txt")
        return 3

    host = os.getenv("ROLEWEAVER_LINE_HOST", "0.0.0.0")
    port_text = os.getenv("ROLEWEAVER_LINE_PORT", "8010")
    try:
        port = int(port_text)
    except ValueError:
        print(f"[RoleWeaver LINE] Invalid ROLEWEAVER_LINE_PORT: {port_text}")
        return 4

    print("[RoleWeaver LINE] Starting LINE bot server...")
    print(f"[RoleWeaver LINE] Local health: http://127.0.0.1:{port}/health")
    print(f"[RoleWeaver LINE] Webhook path: /callback")
    print("[RoleWeaver LINE] Register your public HTTPS tunnel URL as: https://<your-domain>/callback")
    uvicorn.run("line.app:app", host=host, port=port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
