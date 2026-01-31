"""Base scheduler interface for cross-platform support."""

import sys
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from planz.models import Job


class Platform(Enum):
    """Supported platforms for job scheduling."""

    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    DOCKER = "docker"

    @classmethod
    def detect(cls) -> "Platform":
        """Detect the current platform."""
        if sys.platform == "win32":
            return cls.WINDOWS
        elif sys.platform == "darwin":
            return cls.MACOS
        else:
            return cls.LINUX


class BaseScheduler(ABC):
    """Abstract base class for platform-specific schedulers."""

    platform: Platform

    @abstractmethod
    def install(self, job: "Job") -> bool:
        """Install a job to the system scheduler.

        Args:
            job: The job to install.

        Returns:
            True if successful.
        """
        pass

    @abstractmethod
    def uninstall(self, job: "Job") -> bool:
        """Remove a job from the system scheduler.

        Args:
            job: The job to remove.

        Returns:
            True if successful.
        """
        pass

    @abstractmethod
    def list_jobs(self) -> list[str]:
        """List all planz-managed jobs.

        Returns:
            List of job names.
        """
        pass

    def is_job_installed(self, job_name: str) -> bool:
        """Check if a job is installed.

        Args:
            job_name: The job name.

        Returns:
            True if installed.
        """
        return job_name in self.list_jobs()

    @abstractmethod
    def generate_schedule_entry(self, job: "Job") -> str:
        """Generate platform-specific schedule entry for preview.

        Args:
            job: The job.

        Returns:
            Human-readable schedule representation.
        """
        pass

    def is_available(self) -> bool:
        """Check if this scheduler is available on the current system.

        Returns:
            True if available.
        """
        return True


class SchedulerFactory:
    """Factory for creating platform-specific schedulers."""

    _schedulers: dict[Platform, type[BaseScheduler]] = {}

    @classmethod
    def register(cls, platform: Platform, scheduler_class: type[BaseScheduler]) -> None:
        """Register a scheduler for a platform.

        Args:
            platform: The platform.
            scheduler_class: The scheduler class.
        """
        cls._schedulers[platform] = scheduler_class

    @classmethod
    def get_scheduler(
        cls, platform: Optional[Platform] = None, **kwargs
    ) -> BaseScheduler:
        """Get a scheduler for the specified or current platform.

        Args:
            platform: Target platform (auto-detect if None).
            **kwargs: Additional arguments for scheduler initialization.

        Returns:
            A scheduler instance.

        Raises:
            ValueError: If no scheduler is available for the platform.
        """
        if platform is None:
            platform = Platform.detect()

        if platform not in cls._schedulers:
            raise ValueError(f"No scheduler available for platform: {platform.value}")

        return cls._schedulers[platform](**kwargs)

    @classmethod
    def get_available_platforms(cls) -> list[Platform]:
        """Get list of platforms with registered schedulers.

        Returns:
            List of available platforms.
        """
        return list(cls._schedulers.keys())
