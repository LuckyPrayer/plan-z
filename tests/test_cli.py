"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner
from pathlib import Path
import tempfile

from planz.cli import cli


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestCLI:
    """Tests for CLI commands."""

    def test_version(self, runner):
        """Test version command."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "planz" in result.output.lower()

    def test_list_empty(self, runner, temp_config_dir):
        """Test listing with no jobs."""
        result = runner.invoke(cli, ["--config-dir", temp_config_dir, "list"])
        assert result.exit_code == 0
        assert "No jobs found" in result.output

    def test_create_and_list(self, runner, temp_config_dir):
        """Test creating and listing a job."""
        # Create a job
        result = runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "create", "test-job",
                "--schedule", "0 * * * *",
                "--command", "echo hello",
            ],
        )
        assert result.exit_code == 0
        assert "created successfully" in result.output

        # List jobs
        result = runner.invoke(cli, ["--config-dir", temp_config_dir, "list"])
        assert result.exit_code == 0
        assert "test-job" in result.output

    def test_create_with_options(self, runner, temp_config_dir):
        """Test creating a job with all options."""
        result = runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "create", "full-job",
                "--schedule", "0 2 * * *",
                "--command", "/usr/local/bin/backup.sh",
                "--timeout", "3600",
                "--tag", "backup",
                "--tag", "nightly",
                "--env", "TARGET=s3",
                "--workdir", "/opt/backup",
            ],
        )
        assert result.exit_code == 0

    def test_show_job(self, runner, temp_config_dir):
        """Test showing job details."""
        # Create a job
        runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "create", "show-test",
                "--schedule", "0 * * * *",
                "--command", "echo hello",
            ],
        )

        # Show the job
        result = runner.invoke(
            cli,
            ["--config-dir", temp_config_dir, "show", "show-test"],
        )
        assert result.exit_code == 0
        assert "show-test" in result.output
        assert "0 * * * *" in result.output

    def test_show_nonexistent_job(self, runner, temp_config_dir):
        """Test showing a job that doesn't exist."""
        result = runner.invoke(
            cli,
            ["--config-dir", temp_config_dir, "show", "nonexistent"],
        )
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_update_job(self, runner, temp_config_dir):
        """Test updating a job."""
        # Create a job
        runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "create", "update-test",
                "--schedule", "0 * * * *",
                "--command", "old command",
            ],
        )

        # Update the job
        result = runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "update", "update-test",
                "--command", "new command",
            ],
        )
        assert result.exit_code == 0
        assert "updated successfully" in result.output

    def test_delete_job(self, runner, temp_config_dir):
        """Test deleting a job."""
        # Create a job
        runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "create", "delete-test",
                "--schedule", "0 * * * *",
                "--command", "echo test",
            ],
        )

        # Delete with force
        result = runner.invoke(
            cli,
            ["--config-dir", temp_config_dir, "delete", "delete-test", "--force"],
        )
        assert result.exit_code == 0
        assert "deleted successfully" in result.output

    def test_enable_disable_job(self, runner, temp_config_dir):
        """Test enabling and disabling a job."""
        # Create a disabled job
        runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "create", "toggle-test",
                "--schedule", "0 * * * *",
                "--command", "echo test",
                "--disabled",
            ],
        )

        # Enable the job
        result = runner.invoke(
            cli,
            ["--config-dir", temp_config_dir, "enable", "toggle-test"],
        )
        assert result.exit_code == 0
        assert "enabled" in result.output

        # Disable the job
        result = runner.invoke(
            cli,
            ["--config-dir", temp_config_dir, "disable", "toggle-test"],
        )
        assert result.exit_code == 0
        assert "disabled" in result.output

    def test_run_job(self, runner, temp_config_dir):
        """Test running a job immediately."""
        # Create a job
        runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "create", "run-test",
                "--schedule", "0 * * * *",
                "--command", "echo hello",
            ],
        )

        # Run the job
        result = runner.invoke(
            cli,
            ["--config-dir", temp_config_dir, "run", "run-test"],
        )
        assert result.exit_code == 0
        assert "hello" in result.output

    def test_run_dry_run(self, runner, temp_config_dir):
        """Test dry run mode."""
        # Create a job
        runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "create", "dry-run-test",
                "--schedule", "0 * * * *",
                "--command", "echo hello",
            ],
        )

        # Dry run
        result = runner.invoke(
            cli,
            ["--config-dir", temp_config_dir, "run", "dry-run-test", "--dry-run"],
        )
        assert result.exit_code == 0
        assert "Dry run" in result.output

    def test_json_output(self, runner, temp_config_dir):
        """Test JSON output format."""
        # Create a job
        runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "create", "json-test",
                "--schedule", "0 * * * *",
                "--command", "echo test",
            ],
        )

        # List in JSON format
        result = runner.invoke(
            cli,
            ["--json", "--config-dir", temp_config_dir, "list"],
        )
        assert result.exit_code == 0
        # Should be valid JSON with job data
        import json
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "json-test"

    def test_history_empty(self, runner, temp_config_dir):
        """Test history with no executions."""
        result = runner.invoke(
            cli,
            ["--config-dir", temp_config_dir, "history"],
        )
        assert result.exit_code == 0
        assert "No execution history" in result.output

    def test_history_after_run(self, runner, temp_config_dir):
        """Test history after running a job."""
        # Create and run a job
        runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "create", "history-test",
                "--schedule", "0 * * * *",
                "--command", "echo test",
            ],
        )
        runner.invoke(
            cli,
            ["--config-dir", temp_config_dir, "run", "history-test"],
        )

        # Check history
        result = runner.invoke(
            cli,
            ["--config-dir", temp_config_dir, "history"],
        )
        assert result.exit_code == 0
        assert "history-test" in result.output

    def test_import_export(self, runner, temp_config_dir):
        """Test import and export functionality."""
        import tempfile
        import os

        # Create a job
        runner.invoke(
            cli,
            [
                "--config-dir", temp_config_dir,
                "create", "export-test",
                "--schedule", "0 * * * *",
                "--command", "echo test",
            ],
        )

        # Export
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            export_file = f.name

        try:
            result = runner.invoke(
                cli,
                ["--config-dir", temp_config_dir, "export", export_file],
            )
            assert result.exit_code == 0
            assert "Exported 1 job" in result.output

            # Create new config dir and import
            with tempfile.TemporaryDirectory() as new_config:
                result = runner.invoke(
                    cli,
                    ["--config-dir", new_config, "import", export_file],
                )
                assert result.exit_code == 0
                assert "Imported 1 job" in result.output
        finally:
            os.unlink(export_file)
