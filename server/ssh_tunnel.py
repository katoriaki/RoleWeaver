import argparse
import csv
import select
import socket
import socketserver
import sys
import threading
from pathlib import Path


def read_config(path: Path) -> dict:
    values = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = (row.get("key") or "").strip()
            if key:
                values[key] = (row.get("value") or "").strip()
    return values


class ForwardServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(transport, remote_host: str, remote_port: int):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                channel = transport.open_channel(
                    "direct-tcpip",
                    (remote_host, remote_port),
                    self.request.getpeername(),
                )
            except Exception as exc:
                print(f"[RoleWeaver SSH] Could not open channel: {exc}", flush=True)
                return
            if channel is None:
                print("[RoleWeaver SSH] Channel open failed.", flush=True)
                return

            print(
                f"[RoleWeaver SSH] Forward {self.request.getpeername()} -> {remote_host}:{remote_port}",
                flush=True,
            )
            try:
                while True:
                    readable, _, _ = select.select([self.request, channel], [], [])
                    if self.request in readable:
                        data = self.request.recv(16384)
                        if len(data) == 0:
                            break
                        channel.send(data)
                    if channel in readable:
                        data = channel.recv(16384)
                        if len(data) == 0:
                            break
                        self.request.send(data)
            finally:
                channel.close()
                self.request.close()

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="RoleWeaver SSH local port forwarder")
    parser.add_argument("--config", default="server/ssh_tunnel.config.local.csv")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--user")
    parser.add_argument("--password")
    parser.add_argument("--local-host")
    parser.add_argument("--local-port", type=int)
    parser.add_argument("--remote-host")
    parser.add_argument("--remote-port", type=int)
    args = parser.parse_args()

    try:
        import paramiko
    except ModuleNotFoundError:
        print(
            "[RoleWeaver SSH] Missing dependency: paramiko. Install with: "
            "python -m pip install -r server/requirements-tunnel.txt",
            file=sys.stderr,
        )
        return 2

    config_path = Path(args.config)
    config = read_config(config_path) if config_path.exists() else {}

    ssh_host = args.host or config.get("ssh_host") or "ssh-cn-huabei1.ebcloud.com"
    ssh_port = int(args.port or config.get("ssh_port") or 22)
    ssh_user = args.user or config.get("ssh_user") or "root"
    ssh_password = args.password if args.password is not None else config.get("ssh_password", "")
    local_host = args.local_host or config.get("local_host") or "127.0.0.1"
    local_port = int(args.local_port or config.get("local_port") or 8000)
    remote_host = args.remote_host or config.get("remote_host") or "127.0.0.1"
    remote_port = int(args.remote_port or config.get("remote_port") or 8000)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[RoleWeaver SSH] Connecting {ssh_user}@{ssh_host}:{ssh_port}", flush=True)
    client.connect(
        ssh_host,
        port=ssh_port,
        username=ssh_user,
        password=ssh_password or None,
        look_for_keys=True,
        allow_agent=True,
        timeout=30,
    )

    transport = client.get_transport()
    if transport is None:
        raise RuntimeError("SSH transport is not available after connect.")
    transport.set_keepalive(30)

    server = ForwardServer((local_host, local_port), make_handler(transport, remote_host, remote_port))
    print(
        f"[RoleWeaver SSH] Tunnel ready: http://{local_host}:{local_port} -> "
        f"{ssh_user}@{ssh_host}:{ssh_port} -> {remote_host}:{remote_port}",
        flush=True,
    )
    print("[RoleWeaver SSH] Keep this window open. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[RoleWeaver SSH] Stopping tunnel.", flush=True)
    finally:
        server.shutdown()
        server.server_close()
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
