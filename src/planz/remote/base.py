"""Base remote executor interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from planz.models import Host


class HostPlatform(Enum):
    """Remote host platform types."""

    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


@dataclass
class CommandResult:
    """Result of a remote command execution."""

    exit_code: int
    stdout: str
    stderr: str
    duration: Optional[float] = None
    timed_out: bool = False


class RemoteExecutor(ABC):
    """Abstract base class for remote command execution."""

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the remote host.

        Returns:
            True if connection successful.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the remote host."""
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def detect_platform(self) -> HostPlatform:
        """Detect the remote host's platform.

        Returns:
            The detected platform.
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if currently connected.

        Returns:
            True if connected.
        """
        pass

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload a file to the remote host.

        Args:
            local_path: Local file path.
            remote_path: Remote destination path.

        Returns:
            True if successful.
        """
        raise NotImplementedError("File upload not supported by this executor")

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from the remote host.

        Args:
            remote_path: Remote file path.
            local_path: Local destination path.

        Returns:
            True if successful.
        """
        raise NotImplementedError("File download not supported by this executor")


class RemoteExecutorFactory:
    """Factory for creating remote executors based on host configuration."""

    _hosts: dict[str, "Host"] = {}

    @classmethod
    def register_host(cls, host: "Host") -> None:
        """Register a host configuration.

        Args:
            host: Host configuration to register.
        """
        cls._hosts[host.name] = host

    @classmethod
    def get_executor(cls, host_name: str) -> RemoteExecutor:
        """Get an executor for a host by name.

        Args:
            host_name: Name of the host.

        Returns:
            A RemoteExecutor instance.

        Raises:
            ValueError: If the host is not found.
        """
        from planz.remote.local import LocalExecutor

        if host_name in ("localhost", "127.0.0.1", "::1", "local"):
            return LocalExecutor()

        if host_name not in cls._hosts:
            raise ValueError(f"Host '{host_name}' not found. Register it first.")

        return cls.create(cls._hosts[host_name])

    @classmethod
    def create(cls, host: "Host") -> RemoteExecutor:
        """Create an appropriate executor for the given host.

        Args:
            host: Host configuration.

        Returns:
            A RemoteExecutor instance.

        Raises:
            ValueError: If the connection type is not supported.
        """
        from planz.remote.local import LocalExecutor
        from planz.remote.ssh import SSHExecutor

        if host.hostname in ("localhost", "127.0.0.1", "::1") or host.name == "local":
            return LocalExecutor()

        if host.connection_type == "ssh":
            return SSHExecutor(
                hostname=host.hostname,
                port=host.port,
                username=host.username,
                key_file=host.key_file,
                password=host.password,
            )
        elif host.connection_type == "winrm":
            # Future: WinRM support for Windows hosts
            raise ValueError("WinRM connection type not yet implemented")
        else:
            # Default to SSH
            return SSHExecutor(
                hostname=host.hostname,
                port=host.port,
                username=host.username,
                key_file=host.key_file,
                password=host.password,
            )
