from __future__ import annotations

import argparse
import csv
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "ssh_libs"))

import paramiko


DEFAULT_CONFIG = ROOT / "server" / "ssh_tunnel.config.local.csv"
DEFAULT_REMOTE_ROOT = "/root/data/RoleWeaver_A800_Server"
DEFAULT_MODEL_PATH = "/public/huggingface-models/Qwen/Qwen3-Omni-30B-A3B-Instruct"
DEFAULT_DATA_FILE = "data/shiro_persona_sft/shiro_persona_blend.jsonl"


UPLOAD_FILES = [
    "resources/qwen3_omni_training/train_qwen3_omni_text_lora.py",
    "resources/qwen3_omni_training/README.zh-CN.md",
    "server/requirements-a800.txt",
    "role_chat_service.py",
    DEFAULT_DATA_FILE,
    "data/shiro_persona_sft/shiro_persona_blend.report.json",
]


def read_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0] and row[0] != "key":
                values[row[0].strip()] = row[1].strip()
    return values


def run(client: paramiko.SSHClient, command: str, timeout: int = 900, check: bool = True) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if check and code != 0:
        raise RuntimeError(f"remote command failed ({code}):\n{command}\n\nSTDOUT:\n{out}\nSTDERR:\n{err}")
    return code, out, err


def upload_file(client: paramiko.SSHClient, sftp: paramiko.SFTPClient, local_rel: str, remote_root: str) -> None:
    local = (ROOT / local_rel).resolve()
    if not local.exists():
        raise FileNotFoundError(local)
    remote = f"{remote_root.rstrip('/')}/{Path(local_rel).as_posix()}"
    parent = str(Path(remote).parent).replace("\\", "/")
    run(client, f"mkdir -p {shlex.quote(parent)}")
    sftp.put(str(local), remote)
    print(f"[upload] {local_rel} -> {remote}")


def write_remote_text(client: paramiko.SSHClient, sftp: paramiko.SFTPClient, remote_path: str, content: str) -> None:
    parent = str(Path(remote_path).parent).replace("\\", "/")
    run(client, f"mkdir -p {shlex.quote(parent)}")
    with sftp.file(remote_path, "w") as f:
        f.write(content)
    run(client, f"chmod +x {shlex.quote(remote_path)}")


def build_train_script(args: argparse.Namespace, run_dir: str) -> str:
    py = f"{args.remote_root.rstrip('/')}/runtime/server_venv/bin/python"
    data_file = f"{args.remote_root.rstrip('/')}/{args.data_file.strip('/')}"
    output_dir = f"{run_dir}/adapter"
    status_file = f"{run_dir}/training_status.json"
    train_script = f"{args.remote_root.rstrip('/')}/resources/qwen3_omni_training/train_qwen3_omni_text_lora.py"
    command = [
        shlex.quote(py),
        shlex.quote(train_script),
        "--model-path",
        shlex.quote(args.model_path),
        "--data-file",
        shlex.quote(data_file),
        "--output-dir",
        shlex.quote(output_dir),
        "--status-file",
        shlex.quote(status_file),
        "--epochs",
        str(args.epochs),
        "--max-samples",
        str(args.max_samples),
        "--max-length",
        str(args.max_length),
        "--batch-size",
        str(args.batch_size),
        "--gradient-accumulation-steps",
        str(args.gradient_accumulation_steps),
        "--learning-rate",
        str(args.learning_rate),
        "--save-steps",
        str(args.save_steps),
        "--lora-r",
        str(args.lora_r),
        "--lora-alpha",
        str(args.lora_alpha),
        "--lora-dropout",
        str(args.lora_dropout),
        "--quantization",
        args.quantization,
    ]
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"exec > {shlex.quote(run_dir + '/train.log')} 2>&1",
            f"cd {shlex.quote(args.remote_root)}",
            "export PYTHONUNBUFFERED=1",
            "export PYTHONIOENCODING=utf-8",
            "export PYTHONUTF8=1",
            "export HF_HUB_OFFLINE=1",
            "export HF_DATASETS_OFFLINE=1",
            "export CUDA_VISIBLE_DEVICES=0",
            "export TOKENIZERS_PARALLELISM=false",
            f"mkdir -p {shlex.quote(run_dir)}",
            f"{' '.join(command)}",
            "",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload and start remote Qwen3-Omni LoRA training on the A800 server")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT)
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--data-file", default=DEFAULT_DATA_FILE)
    parser.add_argument("--run-name", default="")
    parser.add_argument("--install-deps", action="store_true", default=True)
    parser.add_argument("--skip-install-deps", action="store_true")
    parser.add_argument("--keep-service", action="store_true", help="Do not stop the running RoleWeaver API before training")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--save-steps", type=int, default=25)
    parser.add_argument("--lora-r", type=int, default=4)
    parser.add_argument("--lora-alpha", type=int, default=8)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--quantization", choices=["4bit", "8bit", "bf16", "fp16"], default="4bit")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = read_config(Path(args.config))
    run_name = args.run_name or datetime.now().strftime("omni-shiro-persona-%Y%m%d-%H%M%S")
    run_dir = f"{args.remote_root.rstrip('/')}/training_runs/qwen3_omni_shiro_persona/{run_name}"
    latest_link = f"{args.remote_root.rstrip('/')}/training_runs/qwen3_omni_shiro_persona/latest"

    print(f"[RoleWeaver A800 Training] Connecting {config.get('ssh_user') or 'root'}@{config['ssh_host']}:{config['ssh_port']}")
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

    try:
        sftp = client.open_sftp()
        try:
            for local_rel in UPLOAD_FILES:
                upload_file(client, sftp, local_rel, args.remote_root)
            run_script = f"{run_dir}/run_train.sh"
            write_remote_text(client, sftp, run_script, build_train_script(args, run_dir))
        finally:
            sftp.close()

        if args.install_deps and not args.skip_install_deps:
            print("[remote] installing/updating training dependencies...")
            remote_python = f"{args.remote_root.rstrip('/')}/runtime/server_venv/bin/python"
            cmd = (
                f"{shlex.quote(remote_python)} -m pip install -U peft datasets bitsandbytes "
                "-i https://pypi.tuna.tsinghua.edu.cn/simple"
            )
            code, out, err = run(client, cmd, timeout=1800, check=False)
            print(out)
            if err:
                print(err, file=sys.stderr)
            if code != 0:
                raise RuntimeError("dependency installation failed")

        if not args.keep_service:
            print("[remote] stopping RoleWeaver API to free A800 memory...")
            stop_cmd = (
                f"cd {shlex.quote(args.remote_root)} && "
                "runtime/server_venv/bin/python server/a800_service_manager.py stop --port 8000"
            )
            run(client, stop_cmd, timeout=120, check=False)
            time.sleep(3)

        print("[remote] stopping stale Omni training processes, if any...")
        run(
            client,
            "pkill -f resources/qwen3_omni_training/train_qwen3_omni_text_lora.py || true",
            timeout=30,
            check=False,
        )

        print("[remote] starting background training...")
        latest_parent = latest_link.rsplit("/", 1)[0]
        start_cmd = (
            f"cd {shlex.quote(args.remote_root)} && "
            f"mkdir -p {shlex.quote(latest_parent)} && "
            f"rm -f {shlex.quote(latest_link)} && "
            f"ln -s {shlex.quote(run_dir)} {shlex.quote(latest_link)} && "
            f"setsid bash {shlex.quote(run_dir + '/run_train.sh')} < /dev/null > {shlex.quote(run_dir + '/launcher.log')} 2>&1 & "
            f"echo $! > {shlex.quote(run_dir + '/train.pid')}"
        )
        client.exec_command(start_cmd, timeout=10)
        time.sleep(2)
        print(f"[RoleWeaver A800 Training] started: {run_dir}")
        print("[RoleWeaver A800 Training] monitor: server\\watch_remote_omni_training.bat")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
