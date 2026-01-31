"""Plan-Z CLI - Main entry point."""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from planz import __version__
from planz.models import Job, JobStatus, ExecutionMode
from planz.job_manager import JobManager
from planz.cron_controller import CronController
from planz.executor import JobExecutor

console = Console()
error_console = Console(stderr=True)


def get_config_dir() -> Path:
    """Get the configuration directory."""
    config_dir = Path.home() / ".planz"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_jobs_dir() -> Path:
    """Get the jobs directory."""
    jobs_dir = get_config_dir() / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


def get_logs_dir() -> Path:
    """Get the logs directory."""
    logs_dir = get_config_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


class OutputFormatter:
    """Handles output formatting for CLI."""

    def __init__(self, json_output: bool = False):
        self.json_output = json_output

    def print_jobs(self, jobs: list[Job]) -> None:
        """Print jobs in table or JSON format."""
        if self.json_output:
            data = [job.to_dict() for job in jobs]
            console.print_json(json.dumps(data, indent=2, default=str))
            return

        if not jobs:
            console.print("[yellow]No jobs found.[/yellow]")
            return

        table = Table(title="Managed Jobs")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Host", style="magenta")
        table.add_column("Schedule", style="green")
        table.add_column("Status", style="bold")
        table.add_column("Enabled", style="blue")

        for job in jobs:
            status_icon = {
                JobStatus.SUCCESS: "[green]✅ Success[/green]",
                JobStatus.FAILED: "[red]❌ Failed[/red]",
                JobStatus.TIMEOUT: "[yellow]⏱ Timeout[/yellow]",
                JobStatus.KILLED: "[red]⛔ Killed[/red]",
                JobStatus.RUNNING: "[blue]🔄 Running[/blue]",
                JobStatus.PENDING: "[dim]⏸ Pending[/dim]",
            }.get(job.last_status, "[dim]— Never run[/dim]")

            enabled_icon = "[green]✓[/green]" if job.enabled else "[red]✗[/red]"

            table.add_row(
                job.name,
                job.host or "local",
                job.schedule,
                status_icon,
                enabled_icon,
            )

        console.print(table)

    def print_job_detail(self, job: Job) -> None:
        """Print detailed job information."""
        if self.json_output:
            console.print_json(json.dumps(job.to_dict(), indent=2, default=str))
            return

        console.print(f"\n[bold cyan]Job: {job.name}[/bold cyan]")
        console.print(f"  Host: {job.host or 'local'}")
        console.print(f"  Schedule: {job.schedule}")
        console.print(f"  Command: {job.command}")
        console.print(f"  Enabled: {'Yes' if job.enabled else 'No'}")
        console.print(f"  Timeout: {job.timeout}s" if job.timeout else "  Timeout: None")
        
        if job.env:
            console.print("  Environment:")
            for key, value in job.env.items():
                console.print(f"    {key}={value}")
        
        if job.tags:
            console.print(f"  Tags: {', '.join(job.tags)}")

    def print_success(self, message: str) -> None:
        """Print success message."""
        if not self.json_output:
            console.print(f"[green]✓[/green] {message}")

    def print_error(self, message: str) -> None:
        """Print error message."""
        if self.json_output:
            error_console.print_json(json.dumps({"error": message}))
        else:
            error_console.print(f"[red]✗[/red] {message}")

    def print_warning(self, message: str) -> None:
        """Print warning message."""
        if not self.json_output:
            console.print(f"[yellow]![/yellow] {message}")


@click.group()
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.option("--config-dir", type=click.Path(), help="Custom configuration directory")
@click.version_option(version=__version__, prog_name="planz")
@click.pass_context
def cli(ctx: click.Context, json_output: bool, config_dir: Optional[str]) -> None:
    """Plan-Z - Distributed Cron Management CLI.

    Manage cron jobs on local and remote hosts from a single interface.
    """
    ctx.ensure_object(dict)
    ctx.obj["formatter"] = OutputFormatter(json_output)
    ctx.obj["config_dir"] = Path(config_dir) if config_dir else get_config_dir()
    ctx.obj["jobs_dir"] = ctx.obj["config_dir"] / "jobs"
    ctx.obj["logs_dir"] = ctx.obj["config_dir"] / "logs"

    # Ensure directories exist
    ctx.obj["jobs_dir"].mkdir(parents=True, exist_ok=True)
    ctx.obj["logs_dir"].mkdir(parents=True, exist_ok=True)

    ctx.obj["job_manager"] = JobManager(ctx.obj["jobs_dir"])
    ctx.obj["cron_controller"] = CronController()
    ctx.obj["executor"] = JobExecutor(ctx.obj["logs_dir"])


# --- Job Commands ---

@cli.command("list")
@click.option("--tag", "-t", multiple=True, help="Filter by tag")
@click.option("--host", "-h", help="Filter by host")
@click.option("--enabled/--disabled", default=None, help="Filter by enabled status")
@click.pass_context
def list_jobs(
    ctx: click.Context,
    tag: tuple[str, ...],
    host: Optional[str],
    enabled: Optional[bool],
) -> None:
    """List all managed jobs."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]

    jobs = job_manager.list_jobs(tags=list(tag) if tag else None, host=host, enabled=enabled)
    formatter.print_jobs(jobs)


@cli.command("show")
@click.argument("name")
@click.pass_context
def show_job(ctx: click.Context, name: str) -> None:
    """Show details of a specific job."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]

    job = job_manager.get_job(name)
    if job:
        formatter.print_job_detail(job)
    else:
        formatter.print_error(f"Job '{name}' not found")
        sys.exit(1)


@cli.command("create")
@click.argument("name")
@click.option("--schedule", "-s", required=True, help="Cron schedule expression")
@click.option("--command", "-c", required=True, help="Command to execute")
@click.option("--command-windows", help="Windows-specific command (if different)")
@click.option("--host", "-h", default=None, help="Target host (default: local)")
@click.option("--timeout", "-T", type=int, default=None, help="Execution timeout in seconds")
@click.option("--tag", "-t", multiple=True, help="Job tags")
@click.option("--env", "-e", multiple=True, help="Environment variables (KEY=VALUE)")
@click.option("--workdir", "-w", default=None, help="Working directory")
@click.option("--disabled", is_flag=True, help="Create job in disabled state")
@click.option(
    "--execution-mode",
    type=click.Choice(["native", "docker", "shell"]),
    default="native",
    help="Execution mode (default: native)",
)
@click.option("--docker-image", help="Docker image for docker execution mode")
@click.pass_context
def create_job(
    ctx: click.Context,
    name: str,
    schedule: str,
    command: str,
    command_windows: Optional[str],
    host: Optional[str],
    timeout: Optional[int],
    tag: tuple[str, ...],
    env: tuple[str, ...],
    workdir: Optional[str],
    disabled: bool,
    execution_mode: str,
    docker_image: Optional[str],
) -> None:
    """Create a new job."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]

    # Parse environment variables
    env_dict = {}
    for e in env:
        if "=" in e:
            key, value = e.split("=", 1)
            env_dict[key] = value
        else:
            formatter.print_error(f"Invalid environment variable format: {e}")
            sys.exit(1)

    # Map execution mode string to enum
    exec_mode_map = {
        "native": ExecutionMode.NATIVE,
        "docker": ExecutionMode.DOCKER,
        "shell": ExecutionMode.SHELL,
    }
    exec_mode = exec_mode_map.get(execution_mode, ExecutionMode.NATIVE)

    # Validate docker mode requires image
    if exec_mode == ExecutionMode.DOCKER and not docker_image:
        formatter.print_error("Docker execution mode requires --docker-image option")
        sys.exit(1)

    try:
        job = Job(
            name=name,
            schedule=schedule,
            command=command,
            command_windows=command_windows,
            host=host,
            timeout=timeout,
            tags=list(tag) if tag else [],
            env=env_dict if env_dict else None,
            workdir=workdir,
            enabled=not disabled,
            execution_mode=exec_mode,
            docker_image=docker_image,
        )
        job_manager.create_job(job)
        formatter.print_success(f"Job '{name}' created successfully")
    except ValueError as e:
        formatter.print_error(str(e))
        sys.exit(1)


@cli.command("update")
@click.argument("name")
@click.option("--schedule", "-s", help="Cron schedule expression")
@click.option("--command", "-c", help="Command to execute")
@click.option("--host", "-h", help="Target host")
@click.option("--timeout", "-T", type=int, help="Execution timeout in seconds")
@click.option("--tag", "-t", multiple=True, help="Job tags (replaces existing)")
@click.option("--env", "-e", multiple=True, help="Environment variables (KEY=VALUE)")
@click.option("--workdir", "-w", help="Working directory")
@click.pass_context
def update_job(
    ctx: click.Context,
    name: str,
    schedule: Optional[str],
    command: Optional[str],
    host: Optional[str],
    timeout: Optional[int],
    tag: tuple[str, ...],
    env: tuple[str, ...],
    workdir: Optional[str],
) -> None:
    """Update an existing job."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]

    # Parse environment variables
    env_dict = None
    if env:
        env_dict = {}
        for e in env:
            if "=" in e:
                key, value = e.split("=", 1)
                env_dict[key] = value
            else:
                formatter.print_error(f"Invalid environment variable format: {e}")
                sys.exit(1)

    updates = {
        k: v
        for k, v in {
            "schedule": schedule,
            "command": command,
            "host": host,
            "timeout": timeout,
            "tags": list(tag) if tag else None,
            "env": env_dict,
            "workdir": workdir,
        }.items()
        if v is not None
    }

    if not updates:
        formatter.print_warning("No updates specified")
        return

    try:
        job_manager.update_job(name, **updates)
        formatter.print_success(f"Job '{name}' updated successfully")
    except ValueError as e:
        formatter.print_error(str(e))
        sys.exit(1)


@cli.command("delete")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def delete_job(ctx: click.Context, name: str, force: bool) -> None:
    """Delete a job."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]
    cron_controller: CronController = ctx.obj["cron_controller"]

    job = job_manager.get_job(name)
    if not job:
        formatter.print_error(f"Job '{name}' not found")
        sys.exit(1)

    if not force:
        if not click.confirm(f"Are you sure you want to delete job '{name}'?"):
            formatter.print_warning("Aborted")
            return

    # Remove from cron if installed
    cron_controller.uninstall_job(job)
    job_manager.delete_job(name)
    formatter.print_success(f"Job '{name}' deleted successfully")


@cli.command("enable")
@click.argument("name")
@click.pass_context
def enable_job(ctx: click.Context, name: str) -> None:
    """Enable a job."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]

    try:
        job_manager.update_job(name, enabled=True)
        formatter.print_success(f"Job '{name}' enabled")
    except ValueError as e:
        formatter.print_error(str(e))
        sys.exit(1)


@cli.command("disable")
@click.argument("name")
@click.pass_context
def disable_job(ctx: click.Context, name: str) -> None:
    """Disable a job."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]
    cron_controller: CronController = ctx.obj["cron_controller"]

    job = job_manager.get_job(name)
    if not job:
        formatter.print_error(f"Job '{name}' not found")
        sys.exit(1)

    # Remove from cron when disabled
    cron_controller.uninstall_job(job)
    job_manager.update_job(name, enabled=False)
    formatter.print_success(f"Job '{name}' disabled")


# --- Execution Commands ---

@cli.command("run")
@click.argument("name")
@click.option("--timeout", "-T", type=int, help="Override timeout for this run")
@click.option("--dry-run", is_flag=True, help="Show what would be executed")
@click.pass_context
def run_job(ctx: click.Context, name: str, timeout: Optional[int], dry_run: bool) -> None:
    """Run a job immediately."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]
    executor: JobExecutor = ctx.obj["executor"]

    job = job_manager.get_job(name)
    if not job:
        formatter.print_error(f"Job '{name}' not found")
        sys.exit(1)

    if dry_run:
        console.print(f"\n[bold]Dry run for job: {job.name}[/bold]")
        console.print(f"  Command: {job.command}")
        console.print(f"  Host: {job.host or 'local'}")
        console.print(f"  Timeout: {timeout or job.timeout or 'None'}s")
        if job.env:
            console.print("  Environment:")
            for key, value in job.env.items():
                console.print(f"    {key}={value}")
        return

    console.print(f"[bold]Running job: {job.name}[/bold]")

    result = executor.execute(job, timeout_override=timeout)

    # Update job status
    job_manager.update_job(name, last_status=result.status)

    if result.status == JobStatus.SUCCESS:
        formatter.print_success(f"Job completed successfully (exit code: {result.exit_code})")
    else:
        formatter.print_error(f"Job failed with status: {result.status.value}")

    if result.stdout:
        console.print("\n[bold]stdout:[/bold]")
        console.print(result.stdout)

    if result.stderr:
        console.print("\n[bold]stderr:[/bold]")
        console.print(result.stderr, style="red")


# --- Cron Management Commands ---

@cli.command("apply")
@click.argument("name", required=False)
@click.option("--all", "-a", "apply_all", is_flag=True, help="Apply all enabled jobs")
@click.option("--dry-run", is_flag=True, help="Show what would be applied")
@click.pass_context
def apply_jobs(
    ctx: click.Context, name: Optional[str], apply_all: bool, dry_run: bool
) -> None:
    """Apply/install jobs to cron."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]
    cron_controller: CronController = ctx.obj["cron_controller"]

    if not name and not apply_all:
        formatter.print_error("Specify a job name or use --all to apply all jobs")
        sys.exit(1)

    if apply_all:
        jobs = job_manager.list_jobs(enabled=True)
    else:
        job = job_manager.get_job(name)  # type: ignore
        if not job:
            formatter.print_error(f"Job '{name}' not found")
            sys.exit(1)
        jobs = [job]

    if not jobs:
        formatter.print_warning("No jobs to apply")
        return

    for job in jobs:
        if dry_run:
            entry = cron_controller.generate_cron_entry(job)
            console.print(f"[bold]{job.name}:[/bold] {entry}")
        else:
            if job.host and job.host != "local":
                formatter.print_warning(f"Skipping remote job '{job.name}' (remote not yet supported)")
                continue
            cron_controller.install_job(job)
            formatter.print_success(f"Applied job '{job.name}' to cron")


@cli.command("unapply")
@click.argument("name", required=False)
@click.option("--all", "-a", "unapply_all", is_flag=True, help="Remove all jobs from cron")
@click.pass_context
def unapply_jobs(ctx: click.Context, name: Optional[str], unapply_all: bool) -> None:
    """Remove jobs from cron."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]
    cron_controller: CronController = ctx.obj["cron_controller"]

    if not name and not unapply_all:
        formatter.print_error("Specify a job name or use --all to remove all jobs")
        sys.exit(1)

    if unapply_all:
        jobs = job_manager.list_jobs()
    else:
        job = job_manager.get_job(name)  # type: ignore
        if not job:
            formatter.print_error(f"Job '{name}' not found")
            sys.exit(1)
        jobs = [job]

    for job in jobs:
        cron_controller.uninstall_job(job)
        formatter.print_success(f"Removed job '{job.name}' from cron")


@cli.command("status")
@click.pass_context
def cron_status(ctx: click.Context) -> None:
    """Show cron installation status for all jobs."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]
    cron_controller: CronController = ctx.obj["cron_controller"]

    jobs = job_manager.list_jobs()
    installed = cron_controller.list_installed_jobs()

    if formatter.json_output:
        data = {
            "jobs": [job.name for job in jobs],
            "installed": installed,
        }
        console.print_json(json.dumps(data))
        return

    table = Table(title="Cron Installation Status")
    table.add_column("Job Name", style="cyan")
    table.add_column("Defined", style="blue")
    table.add_column("Installed", style="green")
    table.add_column("Enabled", style="yellow")

    job_names = {job.name for job in jobs}
    all_names = job_names | set(installed)

    for name in sorted(all_names):
        job = job_manager.get_job(name)
        defined = "[green]✓[/green]" if name in job_names else "[red]✗[/red]"
        is_installed = "[green]✓[/green]" if name in installed else "[red]✗[/red]"
        enabled = (
            "[green]✓[/green]"
            if job and job.enabled
            else "[red]✗[/red]"
            if job
            else "[dim]—[/dim]"
        )
        table.add_row(name, defined, is_installed, enabled)

    console.print(table)


# --- Import/Export Commands ---

@cli.command("import")
@click.argument("file", type=click.Path(exists=True))
@click.option("--overwrite", is_flag=True, help="Overwrite existing jobs")
@click.pass_context
def import_jobs(ctx: click.Context, file: str, overwrite: bool) -> None:
    """Import jobs from a YAML file."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]

    try:
        imported = job_manager.import_from_file(Path(file), overwrite=overwrite)
        formatter.print_success(f"Imported {imported} job(s)")
    except Exception as e:
        formatter.print_error(f"Import failed: {e}")
        sys.exit(1)


@cli.command("export")
@click.argument("file", type=click.Path())
@click.option("--name", "-n", multiple=True, help="Export specific jobs")
@click.pass_context
def export_jobs(ctx: click.Context, file: str, name: tuple[str, ...]) -> None:
    """Export jobs to a YAML file."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    job_manager: JobManager = ctx.obj["job_manager"]

    try:
        job_names = list(name) if name else None
        exported = job_manager.export_to_file(Path(file), job_names=job_names)
        formatter.print_success(f"Exported {exported} job(s) to {file}")
    except Exception as e:
        formatter.print_error(f"Export failed: {e}")
        sys.exit(1)


# --- History Commands ---

@cli.command("history")
@click.argument("name", required=False)
@click.option("--limit", "-l", default=10, help="Number of entries to show")
@click.pass_context
def show_history(ctx: click.Context, name: Optional[str], limit: int) -> None:
    """Show execution history."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    executor: JobExecutor = ctx.obj["executor"]

    history = executor.get_history(job_name=name, limit=limit)

    if formatter.json_output:
        console.print_json(json.dumps(history, indent=2, default=str))
        return

    if not history:
        console.print("[yellow]No execution history found.[/yellow]")
        return

    table = Table(title="Execution History")
    table.add_column("Timestamp", style="dim")
    table.add_column("Job", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Exit Code")
    table.add_column("Duration")

    for entry in history:
        status_icon = {
            "success": "[green]✅ Success[/green]",
            "failed": "[red]❌ Failed[/red]",
            "timeout": "[yellow]⏱ Timeout[/yellow]",
            "killed": "[red]⛔ Killed[/red]",
        }.get(entry.get("status", ""), entry.get("status", ""))

        duration = entry.get("duration", "—")
        if isinstance(duration, (int, float)):
            duration = f"{duration:.2f}s"

        table.add_row(
            str(entry.get("timestamp", "—")),
            entry.get("job_name", "—"),
            status_icon,
            str(entry.get("exit_code", "—")),
            duration,
        )

    console.print(table)


def main() -> None:
    """Main entry point."""
    cli(obj={})


# --- Platform Info Command ---

@cli.command("platform")
@click.pass_context
def show_platform(ctx: click.Context) -> None:
    """Show platform information and scheduler details."""
    formatter: OutputFormatter = ctx.obj["formatter"]
    cron_controller: CronController = ctx.obj["cron_controller"]

    info = cron_controller.get_platform_info()

    if formatter.json_output:
        console.print_json(json.dumps(info, indent=2))
        return

    console.print("\n[bold cyan]Platform Information[/bold cyan]")
    console.print(f"  Platform: {info['platform']}")
    console.print(f"  Scheduler: {info['scheduler_type']}")
    console.print(f"  Python: {info['python_version'].split()[0]}")
    console.print(f"  Config Directory: {info['config_dir']}")
    console.print(f"  Logs Directory: {info['logs_dir']}")


if __name__ == "__main__":
    main()
