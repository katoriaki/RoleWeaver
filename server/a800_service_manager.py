#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8000
MAIN_CONFIG = ROOT / "server" / "roleweaver.a800.config.csv"
ADAPTER_CONFIG = ROOT / "server" / "roleweaver.a800.shiro4b_adapter.config.csv"
LOG_DIR = ROOT / "runtime" / "service_logs"
PID_DIR = ROOT / "runtime" / "service_pids"


def listening_socket_inodes(port: int) -> set[str]:
    target_hex = f"{port:04X}"
    inodes: set[str] = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(table).read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 10:
                continue
            local_addr = parts[1]
            state = parts[3]
            inode = parts[9]
            if ":" not in local_addr:
                continue
            local_port = local_addr.rsplit(":", 1)[1].upper()
            if local_port == target_hex and state == "0A":
                inodes.add(inode)
    return inodes


def pids_for_socket_inodes(inodes: Iterable[str]) -> set[int]:
    socket_names = {f"socket:[{inode}]" for inode in inodes}
    pids: set[int] = set()
    if not socket_names:
        return pids
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        fd_dir = proc / "fd"
        try:
            for fd in fd_dir.iterdir():
                try:
                    if os.readlink(fd) in socket_names:
                        pids.add(int(proc.name))
                        break
                except OSError:
                    continue
        except OSError:
            continue
    return pids


def pids_on_port(port: int) -> list[int]:
    return sorted(pids_for_socket_inodes(listening_socket_inodes(port)))


def stop_port(port: int, timeout_seconds: float = 25.0) -> list[int]:
    pids = pids_on_port(port)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        live = []
        for pid in pids:
            try:
                os.kill(pid, 0)
                live.append(pid)
            except ProcessLookupError:
                pass
        if not live:
            return pids
        time.sleep(0.5)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return pids


def health(port: int, timeout_seconds: float = 5.0) -> dict:
    url = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"status": "offline", "error": str(exc)}


def wait_health(port: int, timeout_seconds: float = 900.0) -> dict:
    deadline = time.time() + timeout_seconds
    last = {"status": "offline", "error": "not checked"}
    while time.time() < deadline:
        last = health(port, timeout_seconds=5.0)
        if last.get("status") == "ok":
            return last
        time.sleep(5)
    return last


def start_service(config: Path, port: int, mode_name: str) -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"a800_{mode_name}_{port}.log"
    pid_path = PID_DIR / f"a800_{mode_name}_{port}.pid"
    env = os.environ.copy()
    env.update(
        {
            "ROLEWEAVER_SKIP_INSTALL": "1",
            "ROLEWEAVER_PORT": str(port),
            "ROLEWEAVER_CONFIG_FILE": str(config),
        }
    )
    with log_path.open("ab", buffering=0) as log:
        process = subprocess.Popen(
            ["bash", "server/start_a800_server.sh"],
            cwd=str(ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    pid_path.write_text(str(process.pid), encoding="utf-8")
    return {"pid": process.pid, "log": str(log_path), "config": str(config), "port": port}


def switch(config: Path, port: int, mode_name: str, wait: bool) -> dict:
    stopped = stop_port(port)
    started = start_service(config, port, mode_name)
    result = {"stopped": stopped, "started": started}
    if wait:
        result["health"] = wait_health(port)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Single-GPU RoleWeaver A800 service manager.")
    parser.add_argument(
        "action",
        choices=[
            "status",
            "stop",
            "switch-main",
            "switch-adapter",
            "start-main-sidecar",
            "start-adapter-sidecar",
        ],
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--main-config", default=str(MAIN_CONFIG))
    parser.add_argument("--adapter-config", default=str(ADAPTER_CONFIG))
    parser.add_argument("--wait", action="store_true", help="Wait until /health returns ok.")
    args = parser.parse_args()

    if args.action == "status":
        print(json.dumps({"pids": pids_on_port(args.port), "health": health(args.port)}, ensure_ascii=False, indent=2))
        return 0
    if args.action == "stop":
        print(json.dumps({"stopped": stop_port(args.port)}, ensure_ascii=False, indent=2))
        return 0
    if args.action == "switch-main":
        print(json.dumps(switch(Path(args.main_config), args.port, "main", args.wait), ensure_ascii=False, indent=2))
        return 0
    if args.action == "switch-adapter":
        print(json.dumps(switch(Path(args.adapter_config), args.port, "adapter", args.wait), ensure_ascii=False, indent=2))
        return 0
    if args.action == "start-main-sidecar":
        print(json.dumps(start_service(Path(args.main_config), args.port, "main_sidecar"), ensure_ascii=False, indent=2))
        return 0
    if args.action == "start-adapter-sidecar":
        print(json.dumps(start_service(Path(args.adapter_config), args.port, "adapter_sidecar"), ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
