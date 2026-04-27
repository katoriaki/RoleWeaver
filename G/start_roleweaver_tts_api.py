import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / "runtime" / "python.exe"
SOVITS = ROOT / "SoVITS_weights_v2ProPlus" / "秦谷美铃_e8_s1312.pth"
GPT = ROOT / "GPT_weights_v2ProPlus" / "秦谷美铃-e15.ckpt"


def main() -> int:
    os.chdir(ROOT)
    missing = [path for path in (PYTHON, SOVITS, GPT) if not path.exists()]
    if missing:
        print("[RoleWeaver TTS] Missing required file:")
        for path in missing:
            print(f"  - {path}")
        return 1
    if "--check" in sys.argv:
        print("[RoleWeaver TTS] Check OK.")
        print(f"[RoleWeaver TTS] Python: {PYTHON}")
        print(f"[RoleWeaver TTS] SoVITS: {SOVITS}")
        print(f"[RoleWeaver TTS] GPT: {GPT}")
        return 0

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("language", "zh_CN")

    cmd = [
        str(PYTHON),
        "api.py",
        "-s",
        str(SOVITS),
        "-g",
        str(GPT),
        "-a",
        "127.0.0.1",
        "-p",
        "9880",
        "-d",
        "cuda",
        "-mt",
        "wav",
    ]

    print(f"[RoleWeaver TTS] Working directory: {ROOT}")
    print(f"[RoleWeaver TTS] Python: {PYTHON}")
    print(f"[RoleWeaver TTS] SoVITS: {SOVITS}")
    print(f"[RoleWeaver TTS] GPT: {GPT}")
    print("[RoleWeaver TTS] API: http://127.0.0.1:9880/")
    print("[RoleWeaver TTS] Press Ctrl+C to stop.")
    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == "__main__":
    sys.exit(main())
