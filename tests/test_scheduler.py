"""Tests for cross-platform scheduler backends."""

import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

from planz.models import Job, ExecutionMode
from planz.scheduler.base import BaseScheduler, Platform, SchedulerFactory


class TestPlatform:
    """Tests for Platform enum."""

    def test_platform_values(self):
        """Test platform enum values."""
        assert Platform.LINUX.value == "linux"
        assert Platform.MACOS.value == "macos"
        assert Platform.WINDOWS.value == "windows"
        assert Platform.DOCKER.value == "docker"


class TestSchedulerFactory:
    """Tests for SchedulerFactory."""

    @patch("sys.platform", "linux")
    def test_factory_returns_cron_scheduler_on_linux(self):
        """Test that factory returns CronScheduler on Linux."""
        from planz.scheduler import cron, windows, docker  # noqa: F401

        scheduler = SchedulerFactory.get_scheduler()
        assert scheduler.platform == Platform.LINUX

    @patch("sys.platform", "darwin")
    def test_factory_returns_cron_scheduler_on_macos(self):
        """Test that factory returns CronScheduler on macOS."""
        from planz.scheduler import cron, windows, docker  # noqa: F401

        scheduler = SchedulerFactory.get_scheduler()
        assert scheduler.platform == Platform.MACOS

    @patch("sys.platform", "win32")
    def test_factory_returns_windows_scheduler_on_windows(self):
        """Test that factory returns WindowsTaskScheduler on Windows."""
        from planz.scheduler import cron, windows, docker  # noqa: F401

        scheduler = SchedulerFactory.get_scheduler()
        assert scheduler.platform == Platform.WINDOWS


class TestCronScheduler:
    """Tests for CronScheduler."""

    def test_generate_schedule_entry(self):
        """Test generating a cron entry."""
        from planz.scheduler.cron import CronScheduler

        scheduler = CronScheduler()
        job = Job(
            name="test-job",
            schedule="0 2 * * *",
            command="echo hello",
        )
        entry = scheduler.generate_schedule_entry(job)
        assert "0 2 * * *" in entry
        assert "echo hello" in entry or "planz run" in entry

    def test_generate_entry_with_workdir(self):
        """Test generating entry with working directory."""
        from planz.scheduler.cron import CronScheduler

        scheduler = CronScheduler()
        job = Job(
            name="test-job",
            schedule="0 2 * * *",
            command="./backup.sh",
            workdir="/opt/backup",
        )
        entry = scheduler.generate_schedule_entry(job)
        assert "cd /opt/backup" in entry

    def test_generate_entry_with_env(self):
        """Test generating entry with environment variables."""
        from planz.scheduler.cron import CronScheduler

        scheduler = CronScheduler()
        job = Job(
            name="test-job",
            schedule="0 2 * * *",
            command="backup.sh",
            env={"KEY": "value"},
        )
        entry = scheduler.generate_schedule_entry(job)
        assert "KEY=value" in entry


class TestWindowsTaskScheduler:
    """Tests for WindowsTaskScheduler."""

    def test_cron_to_schtasks_conversion(self):
        """Test converting cron expressions to schtasks format."""
        from planz.scheduler.windows import WindowsTaskScheduler

        scheduler = WindowsTaskScheduler()

        # Test daily at 2 AM
        result = scheduler._parse_cron_to_schtasks("0 2 * * *")
        assert result["schedule_type"] == "DAILY"
        assert result["start_time"] == "02:00"

        # Test every hour
        result = scheduler._parse_cron_to_schtasks("0 * * * *")
        assert result["schedule_type"] == "HOURLY"

        # Test weekly on Monday
        result = scheduler._parse_cron_to_schtasks("0 8 * * 1")
        assert result["schedule_type"] == "WEEKLY"
        assert "MON" in result.get("days", "")

    def test_generate_schedule_entry(self):
        """Test generating a Windows Task Scheduler entry."""
        from planz.scheduler.windows import WindowsTaskScheduler

        scheduler = WindowsTaskScheduler()
        job = Job(
            name="test-job",
            schedule="0 2 * * *",
            command="echo hello",
        )
        entry = scheduler.generate_schedule_entry(job)
        assert "schtasks" in entry
        assert "/CREATE" in entry
        assert "planz-test-job" in entry


class TestDockerScheduler:
    """Tests for DockerScheduler."""

    def test_generate_schedule_entry(self):
        """Test generating a Docker schedule entry."""
        from planz.scheduler.docker import DockerScheduler

        scheduler = DockerScheduler()
        job = Job(
            name="test-job",
            schedule="0 2 * * *",
            command="python /app/script.py",
            execution_mode=ExecutionMode.DOCKER,
            docker_image="python:3.11",
        )
        entry = scheduler.generate_schedule_entry(job)
        assert "docker run" in entry
        assert "python:3.11" in entry

    def test_generate_compose_config(self):
        """Test generating Docker Compose configuration."""
        from planz.scheduler.docker import DockerScheduler

        scheduler = DockerScheduler()
        job = Job(
            name="etl-job",
            schedule="0 3 * * *",
            command="python /app/etl.py",
            execution_mode=ExecutionMode.DOCKER,
            docker_image="python:3.11",
            docker_volumes=["/data:/app/data"],
            env={"DB_HOST": "localhost"},
        )
        config = scheduler.generate_compose_config(job)
        assert "services" in config
        assert "etl-job" in config["services"]
        assert config["services"]["etl-job"]["image"] == "python:3.11"


class TestCrossplatformJobExecution:
    """Tests for cross-platform job execution."""

    def test_job_with_windows_command_override(self):
        """Test that Windows command override is available."""
        job = Job(
            name="cross-platform-job",
            schedule="0 2 * * *",
            command="./backup.sh",
            command_windows="backup.ps1",
        )
        assert job.command == "./backup.sh"
        assert job.command_windows == "backup.ps1"

    def test_job_with_docker_mode(self):
        """Test Docker execution mode job."""
        job = Job(
            name="docker-job",
            schedule="0 3 * * *",
            command="python /app/process.py",
            execution_mode=ExecutionMode.DOCKER,
            docker_image="python:3.11",
        )
        assert job.execution_mode == ExecutionMode.DOCKER
        assert job.docker_image == "python:3.11"

    def test_job_with_remote_mode(self):
        """Test remote execution mode job."""
        job = Job(
            name="remote-job",
            schedule="0 4 * * *",
            command="./deploy.sh",
            execution_mode=ExecutionMode.REMOTE,
            host="prod-server",
        )
        assert job.execution_mode == ExecutionMode.REMOTE
        assert job.host == "prod-server"
