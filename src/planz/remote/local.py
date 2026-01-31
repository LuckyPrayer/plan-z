"""Local command executor."""

import os
import subprocess
import sys
import time
from typing import Optional

from planz.remote.base import CommandResult, HostPlatform, RemoteExecutor


class LocalExecutor(RemoteExecutor):
    """Executes commands on the local machine."""

    def __init__(self):
        """Initialize the local executor."""
        self._connected = True

    def connect(self) -> bool:
        """Local executor is always connected."""
        self._connected = True
        return True

    def disconnect(self) -> None:
        """No-op for local executor."""
        pass

    def is_connected(self) -> bool:
        """Local executor is always connected."""
        return self._connected

    def detect_platform(self) -> HostPlatform:
        """Detect the local platform."""
        if sys.platform == "win32":
            return HostPlatform.WINDOWS
        elif sys.platform == "darwin":
            return HostPlatform.MACOS
        else:
            return HostPlatform.LINUX

    def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        env: Optional[dict[str, str]] = None,
        workdir: Optional[str] = None,
    ) -> CommandResult:
        """Execute a command locally.

        Args:
            command: Command to execute.
            timeout: Execution timeout in seconds.
            env: Environment variables.
            workdir: Working directory.

        Returns:
            CommandResult with exit code and output.
        """
        start_time = time.time()

        # Build environment
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        # Determine shell based on platform
        platform = self.detect_platform()
        if platform == HostPlatform.WINDOWS:
            shell_cmd = ["cmd", "/c", command]
        else:
            shell_cmd = ["/bin/sh", "-c", command]

        try:
            result = subprocess.run(
                shell_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=full_env,
                cwd=workdir,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            duration = time.time() - start_time
            return CommandResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration,
                timed_out=False,
            )

        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            return CommandResult(
                exit_code=-1,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr=f"Command timed out after {timeout} seconds",
                duration=duration,
                timed_out=True,
            )

        except Exception as e:
            duration = time.time() - start_time
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
            )

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Copy a file locally."""
        import shutil
        try:
            shutil.copy2(local_path, remote_path)
            return True
        except Exception:
            return False

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Copy a file locally."""
        return self.upload_file(remote_path, local_path)
