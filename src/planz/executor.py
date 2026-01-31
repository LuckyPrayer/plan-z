"""Job execution functionality."""

import json
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from planz.models import ExecutionResult, Job, JobStatus, ExecutionMode


class JobExecutor:
    """Executes jobs and manages execution history."""

    def __init__(self, logs_dir: Path):
        """Initialize the executor.

        Args:
            logs_dir: Directory for storing execution logs.
        """
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = logs_dir / "history.json"

    def execute(
        self,
        job: Job,
        timeout_override: Optional[int] = None,
        capture_output: bool = True,
    ) -> ExecutionResult:
        """Execute a job.

        Args:
            job: The job to execute.
            timeout_override: Override the job's timeout.
            capture_output: Whether to capture stdout/stderr.

        Returns:
            The execution result.
        """
        # Route to appropriate executor based on execution mode
        if job.execution_mode == ExecutionMode.DOCKER:
            return self._execute_docker(job, timeout_override, capture_output)
        elif job.host and job.host != "local":
            # Remote execution for jobs with non-local host
            return self._execute_remote(job, timeout_override, capture_output)
        else:
            return self._execute_local(job, timeout_override, capture_output)

    def _execute_local(
        self,
        job: Job,
        timeout_override: Optional[int] = None,
        capture_output: bool = True,
    ) -> ExecutionResult:
        """Execute a job locally.

        Args:
            job: The job to execute.
            timeout_override: Override the job's timeout.
            capture_output: Whether to capture stdout/stderr.

        Returns:
            The execution result.
        """
        timeout = timeout_override or job.timeout
        started_at = datetime.now()

        # Build environment
        env = os.environ.copy()
        if job.env:
            env.update(job.env)

        # Add planz-specific env vars
        env["PLANZ_JOB_NAME"] = job.name
        env["PLANZ_JOB_STARTED"] = started_at.isoformat()

        # Choose command based on platform
        command = self._get_platform_command(job)

        try:
            # Determine shell based on OS
            if sys.platform == "win32":
                shell_cmd = ["cmd", "/c", command]
            else:
                shell_cmd = ["/bin/sh", "-c", command]

            process = subprocess.Popen(
                shell_cmd,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE if capture_output else None,
                env=env,
                cwd=job.workdir,
                text=True,
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)
                exit_code = process.returncode
                status = JobStatus.SUCCESS if exit_code == 0 else JobStatus.FAILED

            except subprocess.TimeoutExpired:
                # Kill the process
                self._kill_process(process)
                stdout, stderr = process.communicate()
                exit_code = -1
                status = JobStatus.TIMEOUT
                stderr = (stderr or "") + f"\nProcess timed out after {timeout} seconds"

        except Exception as e:
            stdout = None
            stderr = str(e)
            exit_code = -1
            status = JobStatus.FAILED

        ended_at = datetime.now()
        duration = (ended_at - started_at).total_seconds()

        result = ExecutionResult(
            job_name=job.name,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            started_at=started_at,
            ended_at=ended_at,
            duration=duration,
        )

        # Log the execution
        self._log_execution(result)

        return result

    def _execute_docker(
        self,
        job: Job,
        timeout_override: Optional[int] = None,
        capture_output: bool = True,
    ) -> ExecutionResult:
        """Execute a job in a Docker container.

        Args:
            job: The job to execute.
            timeout_override: Override the job's timeout.
            capture_output: Whether to capture stdout/stderr.

        Returns:
            The execution result.
        """
        timeout = timeout_override or job.timeout
        started_at = datetime.now()

        if not job.docker_image:
            return ExecutionResult(
                job_name=job.name,
                status=JobStatus.FAILED,
                exit_code=-1,
                stderr="Docker execution mode requires docker_image to be set",
                started_at=started_at,
                ended_at=datetime.now(),
                duration=0,
            )

        # Build docker run command
        docker_cmd = ["docker", "run", "--rm"]

        # Add environment variables
        if job.env:
            for key, value in job.env.items():
                docker_cmd.extend(["-e", f"{key}={value}"])

        # Add planz-specific env vars
        docker_cmd.extend(["-e", f"PLANZ_JOB_NAME={job.name}"])
        docker_cmd.extend(["-e", f"PLANZ_JOB_STARTED={started_at.isoformat()}"])

        # Add working directory
        if job.workdir:
            docker_cmd.extend(["-w", job.workdir])

        # Add volume mounts if specified
        if job.docker_volumes:
            for volume in job.docker_volumes:
                docker_cmd.extend(["-v", volume])

        # Add the image and command
        docker_cmd.append(job.docker_image)
        docker_cmd.extend(["/bin/sh", "-c", job.command])

        try:
            process = subprocess.Popen(
                docker_cmd,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE if capture_output else None,
                text=True,
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)
                exit_code = process.returncode
                status = JobStatus.SUCCESS if exit_code == 0 else JobStatus.FAILED

            except subprocess.TimeoutExpired:
                # Kill the container
                subprocess.run(["docker", "kill", f"planz-{job.name}"], capture_output=True)
                stdout, stderr = process.communicate()
                exit_code = -1
                status = JobStatus.TIMEOUT
                stderr = (stderr or "") + f"\nContainer timed out after {timeout} seconds"

        except Exception as e:
            stdout = None
            stderr = str(e)
            exit_code = -1
            status = JobStatus.FAILED

        ended_at = datetime.now()
        duration = (ended_at - started_at).total_seconds()

        result = ExecutionResult(
            job_name=job.name,
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            started_at=started_at,
            ended_at=ended_at,
            duration=duration,
        )

        self._log_execution(result)
        return result

    def _execute_remote(
        self,
        job: Job,
        timeout_override: Optional[int] = None,
        capture_output: bool = True,
    ) -> ExecutionResult:
        """Execute a job on a remote host via SSH.

        Args:
            job: The job to execute.
            timeout_override: Override the job's timeout.
            capture_output: Whether to capture stdout/stderr.

        Returns:
            The execution result.
        """
        from planz.remote.base import RemoteExecutorFactory
        from planz.remote import ssh, local  # noqa: F401

        timeout = timeout_override or job.timeout
        started_at = datetime.now()

        if not job.host or job.host == "local":
            # Fall back to local execution
            return self._execute_local(job, timeout_override, capture_output)

        try:
            # Get appropriate remote executor
            executor = RemoteExecutorFactory.get_executor(job.host)

            # Build environment
            env = {}
            if job.env:
                env.update(job.env)
            env["PLANZ_JOB_NAME"] = job.name
            env["PLANZ_JOB_STARTED"] = started_at.isoformat()

            # Execute command
            command = self._get_platform_command(job)
            cmd_result = executor.execute(
                command,
                env=env,
                workdir=job.workdir,
                timeout=timeout,
            )

            status = JobStatus.SUCCESS if cmd_result.exit_code == 0 else JobStatus.FAILED
            if cmd_result.timed_out:
                status = JobStatus.TIMEOUT

            ended_at = datetime.now()
            duration = (ended_at - started_at).total_seconds()

            result = ExecutionResult(
                job_name=job.name,
                status=status,
                exit_code=cmd_result.exit_code,
                stdout=cmd_result.stdout,
                stderr=cmd_result.stderr,
                started_at=started_at,
                ended_at=ended_at,
                duration=duration,
            )

        except Exception as e:
            result = ExecutionResult(
                job_name=job.name,
                status=JobStatus.FAILED,
                exit_code=-1,
                stderr=f"Remote execution failed: {e}",
                started_at=started_at,
                ended_at=datetime.now(),
                duration=0,
            )

        self._log_execution(result)
        return result

    def _get_platform_command(self, job: Job) -> str:
        """Get the appropriate command for the current platform.

        Args:
            job: The job.

        Returns:
            The command to execute.
        """
        if sys.platform == "win32" and job.command_windows:
            return job.command_windows
        return job.command

    def _kill_process(self, process: subprocess.Popen) -> None:
        """Kill a process and its children.

        Args:
            process: The process to kill.
        """
        if sys.platform == "win32":
            process.kill()
        else:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (OSError, ProcessLookupError):
                process.kill()

    def _log_execution(self, result: ExecutionResult) -> None:
        """Log an execution result.

        Args:
            result: The execution result.
        """
        # Write to job-specific log
        job_log_dir = self.logs_dir / result.job_name
        job_log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = result.started_at.strftime("%Y%m%d_%H%M%S") if result.started_at else "unknown"
        log_file = job_log_dir / f"{timestamp}.json"

        with open(log_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2, default=str)

        # Append to history
        self._append_to_history(result)

    def _append_to_history(self, result: ExecutionResult) -> None:
        """Append an execution to the history file.

        Args:
            result: The execution result.
        """
        history = []
        if self.history_file.exists():
            try:
                with open(self.history_file, "r") as f:
                    history = json.load(f)
            except json.JSONDecodeError:
                history = []

        # Add new entry
        entry = {
            "timestamp": result.started_at.isoformat() if result.started_at else None,
            "job_name": result.job_name,
            "status": result.status.value,
            "exit_code": result.exit_code,
            "duration": result.duration,
        }
        history.insert(0, entry)

        # Keep only last 1000 entries
        history = history[:1000]

        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=2)

    def get_history(
        self,
        job_name: Optional[str] = None,
        limit: int = 10,
        status: Optional[JobStatus] = None,
    ) -> list[dict[str, Any]]:
        """Get execution history.

        Args:
            job_name: Filter by job name.
            limit: Maximum entries to return.
            status: Filter by status.

        Returns:
            List of history entries.
        """
        if not self.history_file.exists():
            return []

        try:
            with open(self.history_file, "r") as f:
                history = json.load(f)
        except json.JSONDecodeError:
            return []

        # Apply filters
        if job_name:
            history = [h for h in history if h.get("job_name") == job_name]
        if status:
            history = [h for h in history if h.get("status") == status.value]

        return history[:limit]

    def get_last_execution(self, job_name: str) -> Optional[dict[str, Any]]:
        """Get the last execution for a job.

        Args:
            job_name: The job name.

        Returns:
            The last execution entry or None.
        """
        history = self.get_history(job_name=job_name, limit=1)
        return history[0] if history else None

    def get_execution_log(
        self, job_name: str, timestamp: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Get a specific execution log.

        Args:
            job_name: The job name.
            timestamp: The execution timestamp (format: YYYYMMDD_HHMMSS).

        Returns:
            The execution log or None.
        """
        job_log_dir = self.logs_dir / job_name
        if not job_log_dir.exists():
            return None

        if timestamp:
            log_file = job_log_dir / f"{timestamp}.json"
            if log_file.exists():
                with open(log_file, "r") as f:
                    return json.load(f)
            return None

        # Get the most recent log
        log_files = sorted(job_log_dir.glob("*.json"), reverse=True)
        if log_files:
            with open(log_files[0], "r") as f:
                return json.load(f)

        return None

    def cleanup_old_logs(self, max_age_days: int = 30) -> int:
        """Clean up old execution logs.

        Args:
            max_age_days: Maximum age of logs to keep.

        Returns:
            Number of logs deleted.
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=max_age_days)
        deleted = 0

        for job_dir in self.logs_dir.iterdir():
            if not job_dir.is_dir():
                continue

            for log_file in job_dir.glob("*.json"):
                try:
                    # Parse timestamp from filename
                    timestamp_str = log_file.stem
                    log_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    if log_time < cutoff:
                        log_file.unlink()
                        deleted += 1
                except (ValueError, OSError):
                    continue

        return deleted
