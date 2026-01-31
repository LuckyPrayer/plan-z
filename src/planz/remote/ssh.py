"""SSH remote executor for Unix and Windows (via OpenSSH) hosts."""

import time
from pathlib import Path
from typing import Optional

from planz.remote.base import CommandResult, HostPlatform, RemoteExecutor


class SSHExecutor(RemoteExecutor):
    """Executes commands on remote hosts via SSH.

    Supports:
    - Linux/Unix hosts
    - macOS hosts
    - Windows hosts with OpenSSH server installed
    """

    def __init__(
        self,
        hostname: str,
        port: int = 22,
        username: Optional[str] = None,
        key_file: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 30,
    ):
        """Initialize the SSH executor.

        Args:
            hostname: Remote hostname or IP address.
            port: SSH port (default: 22).
            username: SSH username.
            key_file: Path to SSH private key file.
            password: SSH password (key_file preferred).
            timeout: Connection timeout in seconds.
        """
        self.hostname = hostname
        self.port = port
        self.username = username
        self.key_file = key_file
        self.password = password
        self.timeout = timeout
        self._client = None
        self._platform: Optional[HostPlatform] = None

    def connect(self) -> bool:
        """Establish SSH connection."""
        try:
            import paramiko

            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": self.hostname,
                "port": self.port,
                "timeout": self.timeout,
            }

            if self.username:
                connect_kwargs["username"] = self.username

            if self.key_file:
                key_path = Path(self.key_file).expanduser()
                connect_kwargs["key_filename"] = str(key_path)
            elif self.password:
                connect_kwargs["password"] = self.password

            self._client.connect(**connect_kwargs)
            return True

        except ImportError:
            raise RuntimeError(
                "paramiko is required for SSH connections. "
                "Install it with: pip install paramiko"
            )
        except Exception as e:
            self._client = None
            raise ConnectionError(f"Failed to connect to {self.hostname}: {e}")

    def disconnect(self) -> None:
        """Close SSH connection."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self._platform = None

    def is_connected(self) -> bool:
        """Check if SSH connection is active."""
        if not self._client:
            return False
        try:
            transport = self._client.get_transport()
            return transport is not None and transport.is_active()
        except Exception:
            return False

    def detect_platform(self) -> HostPlatform:
        """Detect the remote host's platform."""
        if self._platform:
            return self._platform

        if not self.is_connected():
            self.connect()

        # Try to detect platform
        result = self.execute("uname -s", timeout=10)
        if result.exit_code == 0:
            uname = result.stdout.strip().lower()
            if "linux" in uname:
                self._platform = HostPlatform.LINUX
            elif "darwin" in uname:
                self._platform = HostPlatform.MACOS
            else:
                self._platform = HostPlatform.LINUX  # Assume Linux for other Unix
        else:
            # Try Windows detection
            result = self.execute("ver", timeout=10)
            if result.exit_code == 0 and "windows" in result.stdout.lower():
                self._platform = HostPlatform.WINDOWS
            else:
                # Try another Windows check
                result = self.execute("echo %OS%", timeout=10)
                if "windows" in result.stdout.lower():
                    self._platform = HostPlatform.WINDOWS
                else:
                    self._platform = HostPlatform.UNKNOWN

        return self._platform

    def _detect_platform_internal(self) -> None:
        """Internal platform detection without using _build_command to avoid recursion."""
        if self._platform:
            return

        if not self.is_connected():
            self.connect()

        try:
            # Try Unix detection first (uname)
            stdin, stdout, stderr = self._client.exec_command("uname -s", timeout=10)
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code == 0:
                uname = stdout.read().decode("utf-8", errors="replace").strip().lower()
                if "linux" in uname:
                    self._platform = HostPlatform.LINUX
                elif "darwin" in uname:
                    self._platform = HostPlatform.MACOS
                else:
                    self._platform = HostPlatform.LINUX  # Assume Linux for other Unix
                return

            # Try Windows detection (ver command)
            stdin, stdout, stderr = self._client.exec_command("ver", timeout=10)
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code == 0:
                ver_output = stdout.read().decode("utf-8", errors="replace").lower()
                if "windows" in ver_output:
                    self._platform = HostPlatform.WINDOWS
                    return

            # Try another Windows check
            stdin, stdout, stderr = self._client.exec_command("echo %OS%", timeout=10)
            output = stdout.read().decode("utf-8", errors="replace").lower()
            if "windows" in output:
                self._platform = HostPlatform.WINDOWS
            else:
                self._platform = HostPlatform.UNKNOWN
                
        except Exception:
            self._platform = HostPlatform.UNKNOWN

    def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        env: Optional[dict[str, str]] = None,
        workdir: Optional[str] = None,
    ) -> CommandResult:
        """Execute a command on the remote host.

        Args:
            command: Command to execute.
            timeout: Execution timeout in seconds.
            env: Environment variables.
            workdir: Working directory.

        Returns:
            CommandResult with exit code and output.
        """
        if not self.is_connected():
            self.connect()

        start_time = time.time()

        # Build the full command with environment and workdir
        full_command = self._build_command(command, env, workdir)

        try:
            stdin, stdout, stderr = self._client.exec_command(
                full_command,
                timeout=timeout,
            )

            exit_code = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode("utf-8", errors="replace")
            stderr_text = stderr.read().decode("utf-8", errors="replace")

            duration = time.time() - start_time

            return CommandResult(
                exit_code=exit_code,
                stdout=stdout_text,
                stderr=stderr_text,
                duration=duration,
                timed_out=False,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            timed_out = "timed out" in error_msg.lower()

            if timed_out:
                error_msg = f"Command timed out after {timeout} seconds"

            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=error_msg,
                duration=duration,
                timed_out=timed_out,
            )

    def _build_command(
        self,
        command: str,
        env: Optional[dict[str, str]] = None,
        workdir: Optional[str] = None,
        skip_platform_detection: bool = False,
    ) -> str:
        """Build the full command with environment and workdir.

        Handles differences between Unix and Windows shells.
        """
        # Detect platform if not already known (skip during detection itself)
        if not skip_platform_detection and self._platform is None:
            self._detect_platform_internal()
        
        is_windows = self._platform == HostPlatform.WINDOWS

        parts = []

        # Add working directory change
        if workdir:
            if is_windows:
                parts.append(f'cd /d "{workdir}"')
            else:
                parts.append(f'cd "{workdir}"')

        # Add environment variables
        if env:
            if is_windows:
                for key, value in env.items():
                    parts.append(f'set "{key}={value}"')
            else:
                for key, value in env.items():
                    parts.append(f'export {key}="{value}"')

        # Add the actual command
        parts.append(command)

        # Join with appropriate separator
        if is_windows:
            return " && ".join(parts)
        else:
            return " && ".join(parts) if parts[:-1] else command

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload a file to the remote host via SFTP."""
        if not self.is_connected():
            self.connect()

        try:
            sftp = self._client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            return True
        except Exception:
            return False

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from the remote host via SFTP."""
        if not self.is_connected():
            self.connect()

        try:
            sftp = self._client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            return True
        except Exception:
            return False

    def __enter__(self) -> "SSHExecutor":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()
