import shlex
import subprocess
import time
from typing import Optional

from .config import QQVoiceBotConfig


class SSHTunnel:
    def __init__(self, config: QQVoiceBotConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None

    def start(self):
        if not self.config.ssh_enable:
            return
        if self.process and self.process.poll() is None:
            return

        target = f"{self.config.ssh_user}@{self.config.ssh_host}"
        forward = (
            f"{self.config.ssh_local_port}:"
            f"{self.config.ssh_remote_host}:"
            f"{self.config.ssh_remote_port}"
        )
        command = [
            "ssh",
            "-N",
            "-L",
            forward,
            "-p",
            str(self.config.ssh_port),
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=30",
        ]
        if self.config.ssh_identity_file:
            command.extend(["-i", self.config.ssh_identity_file])
        if self.config.ssh_extra_args:
            command.extend(shlex.split(self.config.ssh_extra_args))
        command.append(target)

        self.process = subprocess.Popen(command)
        time.sleep(1.5)
        if self.process.poll() is not None:
            raise RuntimeError("SSH tunnel exited during startup. Check SSH config and credentials.")

    def stop(self):
        if not self.process:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
