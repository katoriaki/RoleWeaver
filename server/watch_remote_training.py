from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "ssh_libs"))

import paramiko


DEFAULT_CONFIG = ROOT / "server" / "ssh_tunnel.config.local.csv"


def read_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0] and row[0] != "key":
                values[row[0].strip()] = row[1].strip()
    return values


def run(client: paramiko.SSHClient, command: str, timeout: int = 30) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch a remote RoleWeaver training run through SSH")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--remote-root", default="/root/data/RoleWeaver_A800_Server")
    parser.add_argument("--run-dir", default="training_runs/qwen3_omni_shiro_persona/latest")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--tail-lines", type=int, default=24)
    args = parser.parse_args()

    config = read_config(Path(args.config))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=config["ssh_host"],
        port=int(config["ssh_port"]),
        username=config.get("ssh_user") or "root",
        password=config.get("ssh_password") or None,
        timeout=20,
        banner_timeout=20,
        auth_timeout=20,
    )

    remote_dir = f"{args.remote_root.rstrip('/')}/{args.run_dir.strip('/')}"
    try:
        while True:
            status_cmd = (
                f"cd {args.remote_root!r} && "
                f"RUN_DIR=$(readlink -f {remote_dir!r} 2>/dev/null || echo {remote_dir!r}); "
                "if [ -f \"$RUN_DIR/training_status.json\" ]; then cat \"$RUN_DIR/training_status.json\"; "
                "else echo '{}'; fi"
            )
            log_cmd = (
                f"cd {args.remote_root!r} && "
                f"RUN_DIR=$(readlink -f {remote_dir!r} 2>/dev/null || echo {remote_dir!r}); "
                f"if [ -f \"$RUN_DIR/train.log\" ]; then tail -n {int(args.tail_lines)} \"$RUN_DIR/train.log\"; fi"
            )
            _, status_text, status_err = run(client, status_cmd)
            _, log_text, log_err = run(client, log_cmd)
            clear_screen()
            print("[RoleWeaver Remote Training Monitor]")
            print(f"remote: {config.get('ssh_user') or 'root'}@{config['ssh_host']}:{config['ssh_port']}")
            print(f"run: {remote_dir}")
            print()
            try:
                status = json.loads(status_text or "{}")
            except json.JSONDecodeError:
                status = {"raw_status": status_text}
            if status:
                for key in [
                    "status",
                    "optimizer_step",
                    "max_optimizer_steps",
                    "loss",
                    "learning_rate",
                    "elapsed_seconds",
                    "checkpoint_path",
                    "final_adapter_path",
                    "updated_at",
                ]:
                    if key in status:
                        print(f"{key}: {status[key]}")
            else:
                print("status: waiting for training_status.json")
            if status_err.strip() or log_err.strip():
                print("\n[stderr]")
                print((status_err + log_err).strip())
            print("\n[log tail]")
            print(log_text.rstrip() or "(no log yet)")
            if status.get("status") in {"completed", "failed", "interrupted"}:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nmonitor stopped; remote training continues.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

