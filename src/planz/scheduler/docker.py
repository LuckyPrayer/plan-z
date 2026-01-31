"""Docker-based scheduler backend."""

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from planz.scheduler.base import BaseScheduler, Platform, SchedulerFactory

if TYPE_CHECKING:
    from planz.models import Job


class DockerScheduler(BaseScheduler):
    """Manages job execution in Docker containers.

    This scheduler runs jobs inside Docker containers, which provides:
    - Consistent execution environment across hosts
    - Isolation and resource limits
    - Easy deployment across different platforms
    """

    platform = Platform.DOCKER
    LABEL_PREFIX = "planz.job"
    DEFAULT_IMAGE = "python:3.11-slim"

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        docker_host: Optional[str] = None,
        default_image: Optional[str] = None,
    ):
        """Initialize the Docker scheduler.

        Args:
            config_dir: Configuration directory for logs and state.
            docker_host: Docker host URL (e.g., unix:///var/run/docker.sock).
            default_image: Default Docker image for jobs.
        """
        self.config_dir = config_dir or Path.home() / ".planz"
        self.logs_dir = self.config_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.docker_host = docker_host
        self.default_image = default_image or self.DEFAULT_IMAGE

    def _docker_cmd(self) -> list[str]:
        """Get the base docker command with optional host."""
        cmd = ["docker"]
        if self.docker_host:
            cmd.extend(["-H", self.docker_host])
        return cmd

    def is_available(self) -> bool:
        """Check if Docker is available."""
        try:
            cmd = self._docker_cmd() + ["version"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return result.returncode == 0
        except Exception:
            return False

    def generate_schedule_entry(self, job: "Job") -> str:
        """Generate a Docker run command preview."""
        image = job.docker_image or self.default_image
        return f"docker run {image} {job.command}"

    def _get_container_name(self, job_name: str) -> str:
        """Get the Docker container name for a job."""
        return f"planz-job-{job_name}"

    def install(self, job: "Job") -> bool:
        """Install a job as a Docker-based scheduled task.

        For Docker, we create a helper script/container that handles scheduling.
        In production, this would integrate with Docker Swarm or Kubernetes CronJobs.
        For the MVP, we create a container config that can be used with external schedulers.
        """
        if not job.enabled:
            return False

        # Create job configuration for Docker execution
        container_name = self._get_container_name(job.name)
        image = job.docker_image or self.default_image

        # Store the job configuration for later execution
        job_config = {
            "name": job.name,
            "container_name": container_name,
            "image": image,
            "command": job.command,
            "schedule": job.schedule,
            "env": job.env or {},
            "workdir": job.workdir,
            "timeout": job.timeout,
            "volumes": job.docker_volumes or [],
        }

        config_file = self.config_dir / "docker_jobs" / f"{job.name}.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, "w") as f:
            json.dump(job_config, f, indent=2)

        return True

    def uninstall(self, job: "Job") -> bool:
        """Remove a Docker job configuration."""
        config_file = self.config_dir / "docker_jobs" / f"{job.name}.json"
        if config_file.exists():
            config_file.unlink()

        # Also stop and remove any running container
        container_name = self._get_container_name(job.name)
        try:
            subprocess.run(
                self._docker_cmd() + ["rm", "-f", container_name],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except Exception:
            pass

        return True

    def list_jobs(self) -> list[str]:
        """List all Docker-based jobs."""
        docker_jobs_dir = self.config_dir / "docker_jobs"
        if not docker_jobs_dir.exists():
            return []

        jobs = []
        for config_file in docker_jobs_dir.glob("*.json"):
            jobs.append(config_file.stem)

        return jobs

    def is_job_installed(self, job_name: str) -> bool:
        """Check if a job is configured for Docker execution."""
        config_file = self.config_dir / "docker_jobs" / f"{job_name}.json"
        return config_file.exists()

    def run_container(
        self,
        job: "Job",
        detach: bool = False,
        remove: bool = True,
    ) -> tuple[int, str, str]:
        """Run a job in a Docker container.

        Args:
            job: The job to run.
            detach: Run container in background.
            remove: Remove container after execution.

        Returns:
            Tuple of (exit_code, stdout, stderr).
        """
        container_name = self._get_container_name(job.name)
        image = job.docker_image or self.default_image

        cmd = self._docker_cmd() + ["run"]

        if detach:
            cmd.append("-d")
        if remove:
            cmd.append("--rm")

        cmd.extend(["--name", container_name])

        # Add labels for identification
        cmd.extend(["--label", f"{self.LABEL_PREFIX}.name={job.name}"])
        cmd.extend(["--label", f"{self.LABEL_PREFIX}.managed=true"])

        # Add environment variables
        if job.env:
            for key, value in job.env.items():
                cmd.extend(["-e", f"{key}={value}"])

        # Add Plan-Z specific environment variables
        cmd.extend(["-e", f"PLANZ_JOB_NAME={job.name}"])

        # Set working directory
        if job.workdir:
            cmd.extend(["-w", job.workdir])

        # Add timeout if specified (using timeout command inside container)
        if job.timeout:
            cmd.extend(["--stop-timeout", str(job.timeout)])

        # Add image and command
        cmd.append(image)

        # Handle shell command
        if job.command:
            cmd.extend(["sh", "-c", job.command])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=job.timeout if job.timeout and not detach else None,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            # Kill the container on timeout
            subprocess.run(
                self._docker_cmd() + ["kill", container_name],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return -1, "", "Container execution timed out"
        except Exception as e:
            return -1, "", str(e)

    def get_running_containers(self) -> list[dict[str, Any]]:
        """Get list of running Plan-Z managed containers.

        Returns:
            List of container info dictionaries.
        """
        try:
            cmd = self._docker_cmd() + [
                "ps",
                "--filter", f"label={self.LABEL_PREFIX}.managed=true",
                "--format", "{{json .}}",
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            containers = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    containers.append(json.loads(line))

            return containers
        except Exception:
            return []

    def generate_compose_config(self, job: "Job") -> dict[str, Any]:
        """Generate a Docker Compose configuration for a job.

        This creates a docker-compose.yml structure that can be used
        with external schedulers or orchestration tools.

        Args:
            job: The job to include.

        Returns:
            Docker Compose configuration dictionary.
        """
        compose: dict[str, Any] = {
            "version": "3.8",
            "services": {},
        }

        service_name = job.name.replace("-", "_")
        image = job.docker_image or self.default_image

        service: dict[str, Any] = {
            "image": image,
            "container_name": self._get_container_name(job.name),
            "command": ["sh", "-c", job.command] if job.command else None,
            "labels": {
                f"{self.LABEL_PREFIX}.name": job.name,
                f"{self.LABEL_PREFIX}.managed": "true",
                f"{self.LABEL_PREFIX}.schedule": job.schedule,
            },
        }

        if job.env:
            service["environment"] = job.env

        if job.workdir:
            service["working_dir"] = job.workdir

        if job.docker_volumes:
            service["volumes"] = job.docker_volumes

        # Remove None values
        service = {k: v for k, v in service.items() if v is not None}

        compose["services"][service_name] = service

        return compose


# Register the scheduler
SchedulerFactory.register(Platform.DOCKER, DockerScheduler)
