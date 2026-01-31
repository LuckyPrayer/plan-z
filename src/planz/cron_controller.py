"""Unified cross-platform cron controller.

This module provides a unified interface to the platform-specific schedulers,
handling Windows Task Scheduler, Unix cron, and Docker-based execution.
"""

import sys
from pathlib import Path
from typing import Optional

from planz.models import Job, ExecutionMode


class CronController:
    """Unified controller for managing scheduled jobs across platforms.

    This controller automatically selects the appropriate backend:
    - Windows: Task Scheduler via schtasks
    - Linux/macOS: cron via crontab
    - Docker: Container-based execution
    """

    # Marker for identifying planz-managed entries
    MARKER_PREFIX = "# planz:"

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the cron controller.

        Args:
            config_dir: Configuration directory for logs and state.
        """
        self.config_dir = config_dir or Path.home() / ".planz"
        self.logs_dir = self.config_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Initialize platform-specific scheduler
        self._scheduler = None
        self._init_scheduler()

    def _init_scheduler(self) -> None:
        """Initialize the appropriate scheduler for the current platform."""
        from planz.scheduler.base import SchedulerFactory
        # Import schedulers to ensure they're registered
        from planz.scheduler import cron, windows, docker  # noqa: F401

        self._scheduler = SchedulerFactory.get_scheduler(config_dir=self.config_dir)

    @property
    def scheduler(self):
        """Get the platform-specific scheduler."""
        return self._scheduler

    def generate_cron_entry(self, job: Job) -> str:
        """Generate a schedule entry for a job.

        Args:
            job: The job to generate an entry for.

        Returns:
            The schedule entry string.
        """
        if job.execution_mode == ExecutionMode.DOCKER:
            from planz.scheduler.docker import DockerScheduler
            docker_sched = DockerScheduler(config_dir=self.config_dir)
            return docker_sched.generate_schedule_entry(job)

        return self._scheduler.generate_schedule_entry(job)

    def install_job(self, job: Job) -> bool:
        """Install a job to the system scheduler.

        Args:
            job: The job to install.

        Returns:
            True if successful.
        """
        if not job.enabled:
            return False

        # For Docker execution mode, use Docker scheduler
        if job.execution_mode == ExecutionMode.DOCKER:
            from planz.scheduler.docker import DockerScheduler
            docker_sched = DockerScheduler(config_dir=self.config_dir)
            return docker_sched.install(job)

        return self._scheduler.install(job)

    def uninstall_job(self, job: Job) -> bool:
        """Remove a job from the system scheduler.

        Args:
            job: The job to remove.

        Returns:
            True if successful.
        """
        # For Docker execution mode, use Docker scheduler
        if job.execution_mode == ExecutionMode.DOCKER:
            from planz.scheduler.docker import DockerScheduler
            docker_sched = DockerScheduler(config_dir=self.config_dir)
            return docker_sched.uninstall(job)

        return self._scheduler.uninstall(job)

    def list_installed_jobs(self) -> list[str]:
        """List all planz-managed jobs in the scheduler.

        Returns:
            List of job names.
        """
        return self._scheduler.list_jobs()

    def is_job_installed(self, job_name: str) -> bool:
        """Check if a job is installed in the scheduler.

        Args:
            job_name: The job name.

        Returns:
            True if installed.
        """
        return job_name in self.list_installed_jobs()

    def sync_all(self, jobs: list[Job]) -> dict[str, bool]:
        """Sync all jobs to the system scheduler.

        Args:
            jobs: List of jobs to sync.

        Returns:
            Dict mapping job name to success status.
        """
        results = {}
        installed = set(self.list_installed_jobs())
        job_names = {j.name for j in jobs}

        # Install/update enabled jobs
        for job in jobs:
            if job.enabled and (job.host is None or job.host == "local"):
                results[job.name] = self.install_job(job)
            elif job.name in installed:
                results[job.name] = self.uninstall_job(job)

        # Remove orphaned entries
        for name in installed - job_names:
            # Create a dummy job for removal
            dummy = Job(name=name, schedule="* * * * *", command="")
            self.uninstall_job(dummy)

        return results

    def get_platform_info(self) -> dict:
        """Get information about the current platform and scheduler.

        Returns:
            Dictionary with platform information.
        """
        from planz.scheduler.base import Platform

        return {
            "platform": self._scheduler.platform.value,
            "scheduler_type": type(self._scheduler).__name__,
            "python_version": sys.version,
            "config_dir": str(self.config_dir),
            "logs_dir": str(self.logs_dir),
        }

