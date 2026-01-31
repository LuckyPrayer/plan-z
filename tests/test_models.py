"""Tests for data models."""

import pytest
from datetime import datetime

from planz.models import (
    Job, JobStatus, ExecutionResult, ScheduleType,
    ExecutionMode, HostPlatform
)


class TestJob:
    """Tests for the Job model."""

    def test_create_basic_job(self):
        """Test creating a basic job."""
        job = Job(
            name="test-job",
            schedule="0 * * * *",
            command="echo hello",
        )
        assert job.name == "test-job"
        assert job.schedule == "0 * * * *"
        assert job.command == "echo hello"
        assert job.enabled is True
        assert job.host is None

    def test_create_job_with_all_fields(self):
        """Test creating a job with all fields."""
        job = Job(
            name="full-job",
            schedule="0 2 * * *",
            command="/usr/local/bin/backup.sh",
            host="db01",
            timeout=3600,
            env={"BACKUP_TARGET": "s3"},
            tags=["backup", "nightly"],
            workdir="/opt/backup",
            enabled=True,
            allow_overlap=False,
            retry_count=3,
            retry_delay=300,
        )
        assert job.name == "full-job"
        assert job.host == "db01"
        assert job.timeout == 3600
        assert job.env == {"BACKUP_TARGET": "s3"}
        assert job.tags == ["backup", "nightly"]
        assert job.workdir == "/opt/backup"
        assert job.retry_count == 3

    def test_job_with_cross_platform_commands(self):
        """Test creating a job with platform-specific commands."""
        job = Job(
            name="cross-platform-job",
            schedule="0 2 * * *",
            command="./backup.sh",
            command_windows="backup.ps1",
        )
        assert job.command == "./backup.sh"
        assert job.command_windows == "backup.ps1"

    def test_job_with_docker_execution(self):
        """Test creating a job with Docker execution mode."""
        job = Job(
            name="docker-job",
            schedule="0 3 * * *",
            command="python /app/etl.py",
            execution_mode=ExecutionMode.DOCKER,
            docker_image="python:3.11",
            docker_volumes=["/data:/app/data"],
        )
        assert job.execution_mode == ExecutionMode.DOCKER
        assert job.docker_image == "python:3.11"
        assert job.docker_volumes == ["/data:/app/data"]

    def test_job_name_validation(self):
        """Test job name validation."""
        # Valid names
        Job(name="my-job", schedule="* * * * *", command="test")
        Job(name="my_job", schedule="* * * * *", command="test")
        Job(name="myJob123", schedule="* * * * *", command="test")

        # Invalid names
        with pytest.raises(ValueError):
            Job(name="my job", schedule="* * * * *", command="test")
        with pytest.raises(ValueError):
            Job(name="my.job", schedule="* * * * *", command="test")
        with pytest.raises(ValueError):
            Job(name="", schedule="* * * * *", command="test")

    def test_job_requires_schedule(self):
        """Test that schedule is required."""
        with pytest.raises(ValueError):
            Job(name="test", schedule="", command="test")

    def test_job_requires_command(self):
        """Test that command is required."""
        with pytest.raises(ValueError):
            Job(name="test", schedule="* * * * *", command="")

    def test_job_to_dict(self):
        """Test converting job to dictionary."""
        job = Job(
            name="test-job",
            schedule="0 * * * *",
            command="echo hello",
            tags=["test"],
        )
        data = job.to_dict()
        assert data["name"] == "test-job"
        assert data["schedule"] == "0 * * * *"
        assert data["command"] == "echo hello"
        assert data["tags"] == ["test"]
        assert data["enabled"] is True

    def test_job_from_dict(self):
        """Test creating job from dictionary."""
        data = {
            "name": "test-job",
            "schedule": "0 * * * *",
            "command": "echo hello",
            "host": "server1",
            "timeout": 300,
            "tags": ["test", "example"],
        }
        job = Job.from_dict(data)
        assert job.name == "test-job"
        assert job.schedule == "0 * * * *"
        assert job.command == "echo hello"
        assert job.host == "server1"
        assert job.timeout == 300
        assert job.tags == ["test", "example"]

    def test_job_roundtrip(self):
        """Test that job survives to_dict/from_dict roundtrip."""
        original = Job(
            name="roundtrip-job",
            schedule="0 2 * * *",
            command="/bin/test",
            host="remote",
            timeout=600,
            env={"KEY": "value"},
            tags=["a", "b"],
        )
        data = original.to_dict()
        restored = Job.from_dict(data)

        assert restored.name == original.name
        assert restored.schedule == original.schedule
        assert restored.command == original.command
        assert restored.host == original.host
        assert restored.timeout == original.timeout
        assert restored.env == original.env
        assert restored.tags == original.tags


class TestExecutionResult:
    """Tests for the ExecutionResult model."""

    def test_create_success_result(self):
        """Test creating a successful execution result."""
        result = ExecutionResult(
            job_name="test-job",
            status=JobStatus.SUCCESS,
            exit_code=0,
            stdout="output",
            stderr="",
            started_at=datetime(2025, 1, 1, 0, 0, 0),
            ended_at=datetime(2025, 1, 1, 0, 0, 5),
            duration=5.0,
        )
        assert result.status == JobStatus.SUCCESS
        assert result.exit_code == 0
        assert result.duration == 5.0

    def test_create_failed_result(self):
        """Test creating a failed execution result."""
        result = ExecutionResult(
            job_name="test-job",
            status=JobStatus.FAILED,
            exit_code=1,
            stderr="error message",
        )
        assert result.status == JobStatus.FAILED
        assert result.exit_code == 1

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = ExecutionResult(
            job_name="test-job",
            status=JobStatus.SUCCESS,
            exit_code=0,
        )
        data = result.to_dict()
        assert data["job_name"] == "test-job"
        assert data["status"] == "success"
        assert data["exit_code"] == 0


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.SUCCESS.value == "success"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.TIMEOUT.value == "timeout"
        assert JobStatus.KILLED.value == "killed"


class TestScheduleType:
    """Tests for ScheduleType enum."""

    def test_schedule_type_values(self):
        """Test schedule type enum values."""
        assert ScheduleType.CRON.value == "cron"
        assert ScheduleType.INTERVAL.value == "interval"
        assert ScheduleType.CALENDAR.value == "calendar"
        assert ScheduleType.ONESHOT.value == "oneshot"


class TestExecutionMode:
    """Tests for ExecutionMode enum."""

    def test_execution_mode_values(self):
        """Test execution mode enum values."""
        assert ExecutionMode.LOCAL.value == "local"
        assert ExecutionMode.REMOTE.value == "remote"
        assert ExecutionMode.DOCKER.value == "docker"


class TestHostPlatform:
    """Tests for HostPlatform enum."""

    def test_host_platform_values(self):
        """Test host platform enum values."""
        assert HostPlatform.LINUX.value == "linux"
        assert HostPlatform.MACOS.value == "macos"
        assert HostPlatform.WINDOWS.value == "windows"
        assert HostPlatform.DOCKER.value == "docker"
