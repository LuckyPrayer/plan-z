"""Tests for job manager."""

import pytest
from pathlib import Path
import tempfile

from planz.job_manager import JobManager
from planz.models import Job


@pytest.fixture
def temp_jobs_dir():
    """Create a temporary directory for jobs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def job_manager(temp_jobs_dir):
    """Create a job manager with temporary directory."""
    return JobManager(temp_jobs_dir)


class TestJobManager:
    """Tests for the JobManager class."""

    def test_create_job(self, job_manager):
        """Test creating a new job."""
        job = Job(
            name="test-job",
            schedule="0 * * * *",
            command="echo hello",
        )
        created = job_manager.create_job(job)
        assert created.name == "test-job"

        # Verify it was saved
        loaded = job_manager.get_job("test-job")
        assert loaded is not None
        assert loaded.name == "test-job"
        assert loaded.schedule == "0 * * * *"
        assert loaded.command == "echo hello"

    def test_create_duplicate_job(self, job_manager):
        """Test that creating a duplicate job fails."""
        job = Job(name="test-job", schedule="0 * * * *", command="echo hello")
        job_manager.create_job(job)

        with pytest.raises(ValueError, match="already exists"):
            job_manager.create_job(job)

    def test_get_nonexistent_job(self, job_manager):
        """Test getting a job that doesn't exist."""
        job = job_manager.get_job("nonexistent")
        assert job is None

    def test_list_jobs(self, job_manager):
        """Test listing jobs."""
        job1 = Job(name="job-a", schedule="0 * * * *", command="a")
        job2 = Job(name="job-b", schedule="0 * * * *", command="b")
        job3 = Job(name="job-c", schedule="0 * * * *", command="c")

        job_manager.create_job(job1)
        job_manager.create_job(job2)
        job_manager.create_job(job3)

        jobs = job_manager.list_jobs()
        assert len(jobs) == 3
        # Should be sorted by name
        assert jobs[0].name == "job-a"
        assert jobs[1].name == "job-b"
        assert jobs[2].name == "job-c"

    def test_list_jobs_filter_by_tag(self, job_manager):
        """Test filtering jobs by tag."""
        job1 = Job(name="job-a", schedule="0 * * * *", command="a", tags=["backup"])
        job2 = Job(name="job-b", schedule="0 * * * *", command="b", tags=["etl"])
        job3 = Job(name="job-c", schedule="0 * * * *", command="c", tags=["backup", "etl"])

        job_manager.create_job(job1)
        job_manager.create_job(job2)
        job_manager.create_job(job3)

        backup_jobs = job_manager.list_jobs(tags=["backup"])
        assert len(backup_jobs) == 2
        assert {j.name for j in backup_jobs} == {"job-a", "job-c"}

        etl_jobs = job_manager.list_jobs(tags=["etl"])
        assert len(etl_jobs) == 2

        both_tags = job_manager.list_jobs(tags=["backup", "etl"])
        assert len(both_tags) == 1
        assert both_tags[0].name == "job-c"

    def test_list_jobs_filter_by_enabled(self, job_manager):
        """Test filtering jobs by enabled status."""
        job1 = Job(name="job-a", schedule="0 * * * *", command="a", enabled=True)
        job2 = Job(name="job-b", schedule="0 * * * *", command="b", enabled=False)

        job_manager.create_job(job1)
        job_manager.create_job(job2)

        enabled_jobs = job_manager.list_jobs(enabled=True)
        assert len(enabled_jobs) == 1
        assert enabled_jobs[0].name == "job-a"

        disabled_jobs = job_manager.list_jobs(enabled=False)
        assert len(disabled_jobs) == 1
        assert disabled_jobs[0].name == "job-b"

    def test_update_job(self, job_manager):
        """Test updating a job."""
        job = Job(name="test-job", schedule="0 * * * *", command="old")
        job_manager.create_job(job)

        job_manager.update_job("test-job", command="new", timeout=300)

        updated = job_manager.get_job("test-job")
        assert updated.command == "new"
        assert updated.timeout == 300

    def test_update_nonexistent_job(self, job_manager):
        """Test updating a job that doesn't exist."""
        with pytest.raises(ValueError, match="not found"):
            job_manager.update_job("nonexistent", command="test")

    def test_delete_job(self, job_manager):
        """Test deleting a job."""
        job = Job(name="test-job", schedule="0 * * * *", command="test")
        job_manager.create_job(job)

        result = job_manager.delete_job("test-job")
        assert result is True

        # Verify it's gone
        assert job_manager.get_job("test-job") is None

    def test_delete_nonexistent_job(self, job_manager):
        """Test deleting a job that doesn't exist."""
        result = job_manager.delete_job("nonexistent")
        assert result is False

    def test_import_single_job(self, job_manager, temp_jobs_dir):
        """Test importing a single job from a file."""
        import_file = temp_jobs_dir / "import.yaml"
        import_file.write_text("""
name: imported-job
schedule: "0 2 * * *"
command: /usr/local/bin/backup.sh
timeout: 3600
tags:
  - backup
  - nightly
""")
        count = job_manager.import_from_file(import_file)
        assert count == 1

        job = job_manager.get_job("imported-job")
        assert job is not None
        assert job.timeout == 3600
        assert job.tags == ["backup", "nightly"]

    def test_import_multiple_jobs(self, job_manager, temp_jobs_dir):
        """Test importing multiple jobs from a file."""
        import_file = temp_jobs_dir / "import.yaml"
        import_file.write_text("""
- name: job-1
  schedule: "0 * * * *"
  command: echo 1

- name: job-2
  schedule: "30 * * * *"
  command: echo 2
""")
        count = job_manager.import_from_file(import_file)
        assert count == 2

        assert job_manager.get_job("job-1") is not None
        assert job_manager.get_job("job-2") is not None

    def test_export_jobs(self, job_manager, temp_jobs_dir):
        """Test exporting jobs to a file."""
        job1 = Job(name="job-a", schedule="0 * * * *", command="a")
        job2 = Job(name="job-b", schedule="0 * * * *", command="b")
        job_manager.create_job(job1)
        job_manager.create_job(job2)

        export_file = temp_jobs_dir / "export.yaml"
        count = job_manager.export_to_file(export_file)
        assert count == 2
        assert export_file.exists()

    def test_validate_invalid_cron(self, job_manager):
        """Test that invalid cron expressions are rejected."""
        job = Job(name="invalid", schedule="invalid cron", command="test")
        with pytest.raises(ValueError, match="Invalid cron expression"):
            job_manager.create_job(job)
