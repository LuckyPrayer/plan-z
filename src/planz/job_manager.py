"""Job management functionality."""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from planz.models import Job


class JobManager:
    """Manages job definitions stored as YAML files."""

    def __init__(self, jobs_dir: Path):
        """Initialize the job manager.

        Args:
            jobs_dir: Directory where job files are stored.
        """
        self.jobs_dir = jobs_dir
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _job_file(self, name: str) -> Path:
        """Get the file path for a job."""
        return self.jobs_dir / f"{name}.yaml"

    def get_job(self, name: str) -> Optional[Job]:
        """Get a job by name.

        Args:
            name: The job name.

        Returns:
            The job if found, None otherwise.
        """
        job_file = self._job_file(name)
        if not job_file.exists():
            return None

        with open(job_file, "r") as f:
            data = yaml.safe_load(f)
            return Job.from_dict(data)

    def list_jobs(
        self,
        tags: Optional[list[str]] = None,
        host: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> list[Job]:
        """List all jobs with optional filtering.

        Args:
            tags: Filter by tags (jobs must have all specified tags).
            host: Filter by host.
            enabled: Filter by enabled status.

        Returns:
            List of matching jobs.
        """
        jobs = []
        for job_file in self.jobs_dir.glob("*.yaml"):
            try:
                with open(job_file, "r") as f:
                    data = yaml.safe_load(f)
                    if data:
                        job = Job.from_dict(data)
                        jobs.append(job)
            except Exception:
                continue

        # Apply filters
        if tags:
            jobs = [j for j in jobs if all(t in j.tags for t in tags)]
        if host is not None:
            jobs = [j for j in jobs if j.host == host or (host == "local" and j.host is None)]
        if enabled is not None:
            jobs = [j for j in jobs if j.enabled == enabled]

        return sorted(jobs, key=lambda j: j.name)

    def create_job(self, job: Job) -> Job:
        """Create a new job.

        Args:
            job: The job to create.

        Returns:
            The created job.

        Raises:
            ValueError: If a job with the same name already exists.
        """
        job_file = self._job_file(job.name)
        if job_file.exists():
            raise ValueError(f"Job '{job.name}' already exists")

        # Validate cron expression
        self._validate_schedule(job.schedule)

        job.created_at = datetime.now()
        job.updated_at = datetime.now()

        with open(job_file, "w") as f:
            yaml.dump(job.to_dict(), f, default_flow_style=False, sort_keys=False)

        return job

    def update_job(self, name: str, **kwargs: Any) -> Job:
        """Update an existing job.

        Args:
            name: The job name.
            **kwargs: Fields to update.

        Returns:
            The updated job.

        Raises:
            ValueError: If the job doesn't exist.
        """
        job = self.get_job(name)
        if not job:
            raise ValueError(f"Job '{name}' not found")

        # Validate schedule if being updated
        if "schedule" in kwargs:
            self._validate_schedule(kwargs["schedule"])

        # Update fields
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)

        job.updated_at = datetime.now()

        with open(self._job_file(name), "w") as f:
            yaml.dump(job.to_dict(), f, default_flow_style=False, sort_keys=False)

        return job

    def delete_job(self, name: str) -> bool:
        """Delete a job.

        Args:
            name: The job name.

        Returns:
            True if deleted, False if not found.
        """
        job_file = self._job_file(name)
        if job_file.exists():
            job_file.unlink()
            return True
        return False

    def import_from_file(self, file_path: Path, overwrite: bool = False) -> int:
        """Import jobs from a YAML file.

        Args:
            file_path: Path to the YAML file.
            overwrite: Whether to overwrite existing jobs.

        Returns:
            Number of jobs imported.
        """
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            return 0

        # Handle both single job and list of jobs
        jobs_data = data if isinstance(data, list) else [data]
        imported = 0

        for job_data in jobs_data:
            if not isinstance(job_data, dict):
                continue

            job = Job.from_dict(job_data)
            job_file = self._job_file(job.name)

            if job_file.exists() and not overwrite:
                continue

            job.created_at = datetime.now()
            job.updated_at = datetime.now()

            with open(job_file, "w") as f:
                yaml.dump(job.to_dict(), f, default_flow_style=False, sort_keys=False)
            imported += 1

        return imported

    def export_to_file(
        self, file_path: Path, job_names: Optional[list[str]] = None
    ) -> int:
        """Export jobs to a YAML file.

        Args:
            file_path: Path to the output file.
            job_names: Specific jobs to export (None for all).

        Returns:
            Number of jobs exported.
        """
        if job_names:
            jobs = [self.get_job(name) for name in job_names]
            jobs = [j for j in jobs if j is not None]
        else:
            jobs = self.list_jobs()

        if not jobs:
            return 0

        # Export without internal fields
        export_data = []
        for job in jobs:
            job_dict = {
                "name": job.name,
                "schedule": job.schedule,
                "command": job.command,
            }
            if job.host:
                job_dict["host"] = job.host
            if job.timeout:
                job_dict["timeout"] = job.timeout
            if job.env:
                job_dict["env"] = job.env
            if job.tags:
                job_dict["tags"] = job.tags
            if job.workdir:
                job_dict["workdir"] = job.workdir
            if not job.enabled:
                job_dict["enabled"] = False
            if job.notify:
                job_dict["notify"] = job.notify

            export_data.append(job_dict)

        with open(file_path, "w") as f:
            yaml.dump(export_data, f, default_flow_style=False, sort_keys=False)

        return len(jobs)

    def _validate_schedule(self, schedule: str) -> None:
        """Validate a cron schedule expression.

        Args:
            schedule: The cron expression.

        Raises:
            ValueError: If the expression is invalid.
        """
        try:
            from croniter import croniter
            croniter(schedule)
        except (ValueError, KeyError) as e:
            raise ValueError(f"Invalid cron expression '{schedule}': {e}")
