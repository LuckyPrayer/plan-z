"""Tests for job executor."""

import pytest
from pathlib import Path
import tempfile
import sys

from planz.executor import JobExecutor
from planz.models import Job, JobStatus


@pytest.fixture
def temp_logs_dir():
    """Create a temporary directory for logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def executor(temp_logs_dir):
    """Create an executor with temporary directory."""
    return JobExecutor(temp_logs_dir)


class TestJobExecutor:
    """Tests for the JobExecutor class."""

    def test_execute_successful_command(self, executor):
        """Test executing a successful command."""
        job = Job(
            name="test-success",
            schedule="0 * * * *",
            command="echo hello",
        )
        result = executor.execute(job)

        assert result.status == JobStatus.SUCCESS
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.duration is not None
        assert result.duration >= 0

    def test_execute_failing_command(self, executor):
        """Test executing a failing command."""
        if sys.platform == "win32":
            command = "exit /b 1"
        else:
            command = "exit 1"

        job = Job(
            name="test-fail",
            schedule="0 * * * *",
            command=command,
        )
        result = executor.execute(job)

        assert result.status == JobStatus.FAILED
        assert result.exit_code == 1

    def test_execute_with_timeout(self, executor):
        """Test executing a command that times out."""
        if sys.platform == "win32":
            command = "ping -n 10 127.0.0.1"
        else:
            command = "sleep 10"

        job = Job(
            name="test-timeout",
            schedule="0 * * * *",
            command=command,
            timeout=1,
        )
        result = executor.execute(job)

        assert result.status == JobStatus.TIMEOUT
        assert "timed out" in result.stderr.lower()

    def test_execute_with_env_vars(self, executor):
        """Test executing a command with environment variables."""
        if sys.platform == "win32":
            command = "echo %TEST_VAR%"
        else:
            command = "echo $TEST_VAR"

        job = Job(
            name="test-env",
            schedule="0 * * * *",
            command=command,
            env={"TEST_VAR": "hello123"},
        )
        result = executor.execute(job)

        assert result.status == JobStatus.SUCCESS
        assert "hello123" in result.stdout

    def test_execution_logs_to_history(self, executor, temp_logs_dir):
        """Test that executions are logged to history."""
        job = Job(
            name="test-history",
            schedule="0 * * * *",
            command="echo test",
        )
        executor.execute(job)

        history = executor.get_history(job_name="test-history")
        assert len(history) == 1
        assert history[0]["job_name"] == "test-history"
        assert history[0]["status"] == "success"

    def test_execution_creates_log_file(self, executor, temp_logs_dir):
        """Test that executions create log files."""
        job = Job(
            name="test-logfile",
            schedule="0 * * * *",
            command="echo logged",
        )
        executor.execute(job)

        job_log_dir = temp_logs_dir / "test-logfile"
        assert job_log_dir.exists()

        log_files = list(job_log_dir.glob("*.json"))
        assert len(log_files) == 1

    def test_get_history_limit(self, executor):
        """Test getting history with a limit."""
        job = Job(
            name="test-limit",
            schedule="0 * * * *",
            command="echo test",
        )

        # Run multiple times
        for _ in range(5):
            executor.execute(job)

        # Get limited history
        history = executor.get_history(job_name="test-limit", limit=3)
        assert len(history) == 3

    def test_get_last_execution(self, executor):
        """Test getting the last execution for a job."""
        job = Job(
            name="test-last",
            schedule="0 * * * *",
            command="echo test",
        )
        executor.execute(job)

        last = executor.get_last_execution("test-last")
        assert last is not None
        assert last["job_name"] == "test-last"

    def test_get_last_execution_nonexistent(self, executor):
        """Test getting last execution for a job that never ran."""
        last = executor.get_last_execution("nonexistent")
        assert last is None

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
    def test_execute_with_workdir(self, executor):
        """Test executing a command in a specific directory."""
        job = Job(
            name="test-workdir",
            schedule="0 * * * *",
            command="pwd",
            workdir="/tmp",
        )
        result = executor.execute(job)

        assert result.status == JobStatus.SUCCESS
        assert "/tmp" in result.stdout
