import os
import importlib.util
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
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("language", "zh_CN")
    env["GPT_SOVITS_HOME"] = str(ROOT)
    config_spec = importlib.util.spec_from_file_location("config", ROOT / "config.py")

    device = os.getenv("ROLEWEAVER_TTS_DEVICE", "cuda").strip() or "cuda"

    cmd = [
        str(PYTHON),
        str(ROOT / "run_local_api.py"),
        "-s",
        str(SOVITS),
        "-g",
        str(GPT),
        "-a",
        "127.0.0.1",
        "-p",
        "9880",
        "-d",
        device,
        "-mt",
        "wav",
    ]
    if device.lower() == "cpu":
        cmd.append("-fp")
        env["is_half"] = "False"
    else:
        env.setdefault("is_half", "True")

    print(f"[RoleWeaver TTS] Working directory: {ROOT}")
    print(f"[RoleWeaver TTS] Python: {PYTHON}")
    print(f"[RoleWeaver TTS] SoVITS: {SOVITS}")
    print(f"[RoleWeaver TTS] GPT: {GPT}")
    print(f"[RoleWeaver TTS] Device: {device}")
    print(f"[RoleWeaver TTS] Config: {config_spec.origin if config_spec else ROOT / 'config.py'}")
    print("[RoleWeaver TTS] API: http://127.0.0.1:9880/")
    print("[RoleWeaver TTS] Press Ctrl+C to stop.")
    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == "__main__":
    sys.exit(main())
