"""Windows Task Scheduler backend."""

import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from planz.scheduler.base import BaseScheduler, Platform, SchedulerFactory

if TYPE_CHECKING:
    from planz.models import Job


class WindowsTaskScheduler(BaseScheduler):
    """Manages Windows Task Scheduler entries for jobs."""

    platform = Platform.WINDOWS
    TASK_FOLDER = "\\Plan-Z"
    TASK_PREFIX = "planz_"

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the Windows Task Scheduler.

        Args:
            config_dir: Configuration directory for logs and state.
        """
        self.config_dir = config_dir or Path.home() / ".planz"
        self.logs_dir = self.config_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        """Check if Task Scheduler is available."""
        if sys.platform != "win32":
            return False
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/?"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return result.returncode == 0
        except Exception:
            return False

    def generate_schedule_entry(self, job: "Job") -> str:
        """Generate a human-readable schedule description."""
        return f"Windows Task: {self._get_task_name(job.name)} | Schedule: {job.schedule}"

    def _get_task_name(self, job_name: str) -> str:
        """Get the Windows task name for a job."""
        return f"{self.TASK_PREFIX}{job_name}"

    def _get_full_task_path(self, job_name: str) -> str:
        """Get the full task path including folder."""
        return f"{self.TASK_FOLDER}\\{self._get_task_name(job_name)}"

    def _find_planz_executable(self) -> str:
        """Find the planz executable path."""
        if getattr(sys, "frozen", False):
            return sys.executable

        try:
            result = subprocess.run(
                ["where", "planz"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except Exception:
            pass

        return f'"{sys.executable}" -m planz'

    def _ensure_task_folder(self) -> None:
        """Ensure the Plan-Z task folder exists."""
        try:
            # Check if folder exists
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", self.TASK_FOLDER],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0:
                # Create a dummy task to create the folder, then delete it
                # Windows creates the folder automatically when a task is created
                pass
        except Exception:
            pass

    def install(self, job: "Job") -> bool:
        """Install a job to Windows Task Scheduler."""
        if not job.enabled:
            return False

        self._ensure_task_folder()

        # First, remove existing task if present
        self.uninstall(job)

        task_name = self._get_task_name(job.name)
        planz_path = self._find_planz_executable()

        # Build command - use Windows-specific command if provided
        job_command = job.command_windows if job.command_windows else job.command
        command = f'{planz_path} run "{job.name}"'

        # Convert cron to schtasks parameters
        try:
            sched_params = self._parse_cron_to_schtasks(job.schedule)
        except ValueError:
            # Fall back to daily if cron parse fails
            sched_params = {"schedule_type": "DAILY", "start_time": "00:00"}

        # Build schtasks command
        cmd = [
            "schtasks", "/Create",
            "/TN", task_name,
            "/TR", command,
            "/SC", sched_params["schedule_type"],
            "/F",  # Force overwrite
        ]

        if "modifier" in sched_params:
            cmd.extend(["/MO", sched_params["modifier"]])
        if "days" in sched_params:
            cmd.extend(["/D", sched_params["days"]])
        if "start_time" in sched_params:
            cmd.extend(["/ST", sched_params["start_time"]])

        # Set working directory if specified
        if job.workdir:
            # schtasks doesn't directly support workdir, we handle it in the command
            command = f'cd /d "{job.workdir}" && {command}'
            cmd[cmd.index("/TR") + 1] = f'cmd /c "{command}"'

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return result.returncode == 0
        except Exception as e:
            raise RuntimeError(f"Failed to create scheduled task: {e}")

    def uninstall(self, job: "Job") -> bool:
        """Remove a job from Windows Task Scheduler."""
        task_name = self._get_task_name(job.name)

        try:
            result = subprocess.run(
                ["schtasks", "/Delete", "/TN", task_name, "/F"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            # Return True even if task didn't exist (returncode might be non-zero)
            return True
        except Exception:
            return False

    def list_jobs(self) -> list[str]:
        """List all planz-managed jobs in Task Scheduler."""
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode != 0:
                return []

            jobs = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                # CSV format: "TaskName","Next Run Time","Status"
                parts = line.split('","')
                if parts:
                    task_name = parts[0].strip('"')
                    if task_name.startswith(self.TASK_PREFIX):
                        job_name = task_name[len(self.TASK_PREFIX):]
                        jobs.append(job_name)
                    elif f"\\{self.TASK_PREFIX}" in task_name:
                        # Handle full path format
                        job_name = task_name.split(self.TASK_PREFIX)[-1]
                        jobs.append(job_name)

            return jobs
        except Exception:
            return []

    def _parse_cron_to_schtasks(self, schedule: str) -> dict[str, str]:
        """Convert cron expression to schtasks parameters.

        Args:
            schedule: Cron expression (minute hour day month weekday).

        Returns:
            Dictionary with schedule_type, start_time, modifier, days parameters.
        """
        parts = schedule.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {schedule}")

        minute, hour, day, month, weekday = parts
        params = {}

        # Handle common patterns
        if minute == "*" and hour == "*":
            # Every minute
            params["schedule_type"] = "MINUTE"
            params["modifier"] = "1"
        elif minute != "*" and hour == "*":
            # Every hour at specific minute
            params["schedule_type"] = "HOURLY"
            params["start_time"] = f"00:{minute.zfill(2)}"
        elif minute != "*" and hour != "*" and day == "*" and weekday == "*":
            # Daily at specific time
            params["schedule_type"] = "DAILY"
            params["start_time"] = f"{hour.zfill(2)}:{minute.zfill(2)}"
        elif weekday != "*" and weekday != "0-6":
            # Weekly on specific days
            params["schedule_type"] = "WEEKLY"
            params["start_time"] = f"{hour.zfill(2) if hour != '*' else '00'}:{minute.zfill(2) if minute != '*' else '00'}"
            # Convert cron weekday (0=Sun) to schtasks (SUN, MON, etc.)
            day_map = {
                "0": "SUN", "1": "MON", "2": "TUE", "3": "WED",
                "4": "THU", "5": "FRI", "6": "SAT", "7": "SUN"
            }
            if weekday in day_map:
                params["days"] = day_map[weekday]
            else:
                # Handle ranges like 1-5
                params["days"] = "MON,TUE,WED,THU,FRI"
        elif day != "*" and month != "*":
            # Monthly on specific day
            params["schedule_type"] = "MONTHLY"
            params["days"] = day
            params["start_time"] = f"{hour.zfill(2) if hour != '*' else '00'}:{minute.zfill(2) if minute != '*' else '00'}"
        else:
            # Default to daily
            params["schedule_type"] = "DAILY"
            params["start_time"] = f"{hour.zfill(2) if hour != '*' else '00'}:{minute.zfill(2) if minute != '*' else '00'}"

        return params

    def is_job_installed(self, job_name: str) -> bool:
        """Check if a job is installed in Task Scheduler."""
        task_name = self._get_task_name(job_name)
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", task_name],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        except Exception:
            return False

    def run_task_now(self, job_name: str) -> bool:
        """Manually trigger a scheduled task to run immediately.

        Args:
            job_name: The job name.

        Returns:
            True if triggered successfully.
        """
        task_name = self._get_task_name(job_name)
        try:
            result = subprocess.run(
                ["schtasks", "/Run", "/TN", task_name],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        except Exception:
            return False


# Register the scheduler
SchedulerFactory.register(Platform.WINDOWS, WindowsTaskScheduler)
