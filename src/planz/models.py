"""Plan-Z data models with cross-platform support."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class JobStatus(Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    KILLED = "killed"


class ScheduleType(Enum):
    """Schedule type for jobs."""

    CRON = "cron"
    INTERVAL = "interval"
    CALENDAR = "calendar"
    ONESHOT = "oneshot"


class ExecutionMode(Enum):
    """How the job should be executed."""

    NATIVE = "native"      # Use host's native scheduler (cron/Task Scheduler)
    DOCKER = "docker"      # Run in a Docker container
    SHELL = "shell"        # Direct shell execution (for manual runs)


class HostPlatform(Enum):
    """Host operating system platform."""

    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    AUTO = "auto"          # Auto-detect on connection


@dataclass
class Job:
    """Represents a managed scheduled job with cross-platform support."""

    name: str
    schedule: str
    command: str
    host: Optional[str] = None
    timeout: Optional[int] = None
    env: Optional[dict[str, str]] = None
    tags: list[str] = field(default_factory=list)
    workdir: Optional[str] = None
    enabled: bool = True
    allow_overlap: bool = False
    retry_count: int = 0
    retry_delay: int = 60
    notify: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_status: Optional[JobStatus] = None
    last_run: Optional[datetime] = None
    schedule_type: ScheduleType = ScheduleType.CRON

    # Cross-platform execution options
    execution_mode: ExecutionMode = ExecutionMode.NATIVE

    # Docker-specific options
    docker_image: Optional[str] = None
    docker_volumes: Optional[list[str]] = None
    docker_network: Optional[str] = None

    # Platform-specific command overrides
    command_windows: Optional[str] = None  # Override command for Windows hosts
    command_unix: Optional[str] = None     # Override command for Unix hosts

    def __post_init__(self) -> None:
        """Validate job configuration."""
        if not self.name:
            raise ValueError("Job name is required")
        if not self.schedule:
            raise ValueError("Schedule is required")
        if not self.command:
            raise ValueError("Command is required")

        # Validate name format (alphanumeric, dash, underscore)
        import re
        if not re.match(r"^[a-zA-Z0-9_-]+$", self.name):
            raise ValueError(
                "Job name must contain only alphanumeric characters, dashes, and underscores"
            )

        # Docker mode requires an image
        if self.execution_mode == ExecutionMode.DOCKER and not self.docker_image:
            self.docker_image = "python:3.11-slim"  # Default image

        # Set timestamps
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def get_command_for_platform(self, platform: HostPlatform) -> str:
        """Get the appropriate command for the target platform.

        Args:
            platform: Target host platform.

        Returns:
            The command string appropriate for the platform.
        """
        if platform == HostPlatform.WINDOWS and self.command_windows:
            return self.command_windows
        elif platform in (HostPlatform.LINUX, HostPlatform.MACOS) and self.command_unix:
            return self.command_unix
        return self.command

    def to_dict(self) -> dict[str, Any]:
        """Convert job to dictionary."""
        return {
            "name": self.name,
            "schedule": self.schedule,
            "command": self.command,
            "host": self.host,
            "timeout": self.timeout,
            "env": self.env,
            "tags": self.tags,
            "workdir": self.workdir,
            "enabled": self.enabled,
            "allow_overlap": self.allow_overlap,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "notify": self.notify,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_status": self.last_status.value if self.last_status else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "schedule_type": self.schedule_type.value,
            "execution_mode": self.execution_mode.value,
            "docker_image": self.docker_image,
            "docker_volumes": self.docker_volumes,
            "docker_network": self.docker_network,
            "command_windows": self.command_windows,
            "command_unix": self.command_unix,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        """Create job from dictionary."""
        # Handle datetime fields
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)

        last_run = data.get("last_run")
        if isinstance(last_run, str):
            last_run = datetime.fromisoformat(last_run)

        # Handle status enum
        last_status = data.get("last_status")
        if isinstance(last_status, str):
            last_status = JobStatus(last_status)

        # Handle schedule type enum
        schedule_type = data.get("schedule_type", "cron")
        if isinstance(schedule_type, str):
            schedule_type = ScheduleType(schedule_type)

        # Handle execution mode enum
        execution_mode = data.get("execution_mode", "native")
        if isinstance(execution_mode, str):
            execution_mode = ExecutionMode(execution_mode)

        return cls(
            name=data["name"],
            schedule=data["schedule"],
            command=data["command"],
            host=data.get("host"),
            timeout=data.get("timeout"),
            env=data.get("env"),
            tags=data.get("tags", []),
            workdir=data.get("workdir"),
            enabled=data.get("enabled", True),
            allow_overlap=data.get("allow_overlap", False),
            retry_count=data.get("retry_count", 0),
            retry_delay=data.get("retry_delay", 60),
            notify=data.get("notify"),
            created_at=created_at,
            updated_at=updated_at,
            last_status=last_status,
            last_run=last_run,
            schedule_type=schedule_type,
            execution_mode=execution_mode,
            docker_image=data.get("docker_image"),
            docker_volumes=data.get("docker_volumes"),
            docker_network=data.get("docker_network"),
            command_windows=data.get("command_windows"),
            command_unix=data.get("command_unix"),
        )


@dataclass
class ExecutionResult:
    """Result of a job execution."""

    job_name: str
    status: JobStatus
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "job_name": self.job_name,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration": self.duration,
            "error_message": self.error_message,
        }


@dataclass
class Host:
    """Represents a target host for job execution with cross-platform support."""

    name: str
    hostname: str
    port: int = 22
    username: Optional[str] = None
    key_file: Optional[str] = None
    password: Optional[str] = None  # For non-key auth (use key_file when possible)
    enabled: bool = True
    platform: HostPlatform = HostPlatform.AUTO  # Auto-detect or specify
    connection_type: str = "ssh"  # ssh, winrm (future), local

    # Platform-specific settings
    shell: Optional[str] = None  # Override default shell (e.g., powershell, bash)
    planz_path: Optional[str] = None  # Path to planz on remote host

    def to_dict(self) -> dict[str, Any]:
        """Convert host to dictionary."""
        return {
            "name": self.name,
            "hostname": self.hostname,
            "port": self.port,
            "username": self.username,
            "key_file": self.key_file,
            "enabled": self.enabled,
            "platform": self.platform.value,
            "connection_type": self.connection_type,
            "shell": self.shell,
            "planz_path": self.planz_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Host":
        """Create host from dictionary."""
        platform = data.get("platform", "auto")
        if isinstance(platform, str):
            platform = HostPlatform(platform)

        return cls(
            name=data["name"],
            hostname=data["hostname"],
            port=data.get("port", 22),
            username=data.get("username"),
            key_file=data.get("key_file"),
            password=data.get("password"),
            enabled=data.get("enabled", True),
            platform=platform,
            connection_type=data.get("connection_type", "ssh"),
            shell=data.get("shell"),
            planz_path=data.get("planz_path"),
        )

    def is_local(self) -> bool:
        """Check if this host represents the local machine."""
        return (
            self.name == "local"
            or self.hostname in ("localhost", "127.0.0.1", "::1")
            or self.connection_type == "local"
        )
