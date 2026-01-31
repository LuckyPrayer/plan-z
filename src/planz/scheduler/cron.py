"""Unix cron scheduler backend."""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from planz.scheduler.base import BaseScheduler, Platform, SchedulerFactory

if TYPE_CHECKING:
    from planz.models import Job


class CronScheduler(BaseScheduler):
    """Manages system cron entries for jobs on Unix systems."""

    platform = Platform.LINUX
    MARKER_PREFIX = "# planz:"

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the cron scheduler.

        Args:
            config_dir: Configuration directory for logs and state.
        """
        self.config_dir = config_dir or Path.home() / ".planz"
        self.logs_dir = self.config_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        """Check if cron is available."""
        try:
            result = subprocess.run(
                ["which", "crontab"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def generate_schedule_entry(self, job: "Job") -> str:
        """Generate a cron entry for a job."""
        wrapper_cmd = self._build_wrapper_command(job)

        # Add environment variables
        env_prefix = ""
        if job.env:
            env_parts = [f"{k}={v}" for k, v in job.env.items()]
            env_prefix = " ".join(env_parts) + " "

        # Add working directory
        cd_prefix = ""
        if job.workdir:
            cd_prefix = f"cd {job.workdir} && "

        full_command = f"{cd_prefix}{env_prefix}{wrapper_cmd}"
        return f"{job.schedule} {full_command}"

    def _build_wrapper_command(self, job: "Job") -> str:
        """Build the wrapper command for job execution."""
        planz_path = self._find_planz_executable()
        wrapper_cmd = f'{planz_path} run "{job.name}" 2>&1'

        if job.timeout:
            wrapper_cmd = f"timeout {job.timeout} {wrapper_cmd}"

        return wrapper_cmd

    def _find_planz_executable(self) -> str:
        """Find the planz executable path."""
        if getattr(sys, "frozen", False):
            return sys.executable

        try:
            result = subprocess.run(
                ["which", "planz"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except Exception:
            pass

        return f"{sys.executable} -m planz"

    def install(self, job: "Job") -> bool:
        """Install a job to system cron."""
        if not job.enabled:
            return False

        current_crontab = self._get_crontab()
        lines = current_crontab.split("\n")
        new_lines = []
        skip_next = False

        for line in lines:
            if skip_next:
                skip_next = False
                continue
            if line.strip() == f"{self.MARKER_PREFIX}{job.name}":
                skip_next = True
                continue
            new_lines.append(line)

        marker = f"{self.MARKER_PREFIX}{job.name}"
        entry = self.generate_schedule_entry(job)
        new_lines.extend([marker, entry])

        new_crontab = "\n".join(new_lines)
        self._set_crontab(new_crontab)
        return True

    def uninstall(self, job: "Job") -> bool:
        """Remove a job from system cron."""
        current_crontab = self._get_crontab()
        lines = current_crontab.split("\n")
        new_lines = []
        skip_next = False

        for line in lines:
            if skip_next:
                skip_next = False
                continue
            if line.strip() == f"{self.MARKER_PREFIX}{job.name}":
                skip_next = True
                continue
            new_lines.append(line)

        new_crontab = "\n".join(new_lines)
        self._set_crontab(new_crontab)
        return True

    def list_jobs(self) -> list[str]:
        """List all planz-managed jobs in cron."""
        current_crontab = self._get_crontab()
        pattern = re.compile(rf"^{re.escape(self.MARKER_PREFIX)}(.+)$")

        jobs = []
        for line in current_crontab.split("\n"):
            match = pattern.match(line.strip())
            if match:
                jobs.append(match.group(1))

        return jobs

    def is_job_installed(self, job_name: str) -> bool:
        """Check if a job is installed in cron."""
        return job_name in self.list_installed_jobs()

    def _get_crontab(self) -> str:
        """Get the current user's crontab."""
        try:
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout
            return ""
        except Exception:
            return ""

    def _set_crontab(self, content: str) -> None:
        """Set the current user's crontab."""
        lines = [line for line in content.split("\n") if line.strip() or line == ""]
        content = "\n".join(lines)
        if content and not content.endswith("\n"):
            content += "\n"

        process = subprocess.Popen(
            ["crontab", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _, stderr = process.communicate(input=content)

        if process.returncode != 0:
            raise RuntimeError(f"Failed to set crontab: {stderr}")


# Register the scheduler
SchedulerFactory.register(Platform.LINUX, CronScheduler)
SchedulerFactory.register(Platform.MACOS, CronScheduler)
