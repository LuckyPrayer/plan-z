# Plan-Z Quick Start Guide

This guide helps you get started with Plan-Z quickly.

## Installation

```bash
# Create a virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install in development mode
pip install -e .
```

## Basic Usage

### Create a Job

```bash
# Simple job
planz create my-job -s "0 * * * *" -c "echo hello"

# Job with timeout and tags
planz create backup-job \
  -s "0 2 * * *" \
  -c "/scripts/backup.sh" \
  -T 3600 \
  -t backup \
  -t nightly
```

### List Jobs

```bash
# List all jobs
planz list

# Filter by tag
planz list -t backup

# JSON output
planz --json list
```

### Run a Job Manually

```bash
# Run immediately
planz run my-job

# Dry run (show what would happen)
planz run my-job --dry-run
```

### Apply Jobs to Cron

```bash
# Apply a single job
planz apply my-job

# Apply all enabled jobs
planz apply --all

# Preview without changes
planz apply --all --dry-run
```

### View Job Details

```bash
planz show my-job
```

### View Execution History

```bash
# All history
planz history

# For a specific job
planz history my-job
```

### Enable/Disable Jobs

```bash
planz enable my-job
planz disable my-job
```

### Delete a Job

```bash
planz delete my-job
```

## Configuration

Plan-Z stores its configuration in `~/.planz/`:

```
~/.planz/
├── jobs/          # Job definition files (YAML)
└── logs/          # Execution logs
    ├── history.json
    └── <job-name>/
        └── <timestamp>.json
```

## Import/Export

```bash
# Export jobs
planz export jobs.yaml

# Import jobs
planz import jobs.yaml

# Import with overwrite
planz import jobs.yaml --overwrite
```

## JSON Output

All commands support `--json` for scripting:

```bash
planz --json list | jq '.[] | .name'
```

## Next Steps

- See the [README](readme.md) for full documentation
- Check [examples/jobs/](examples/jobs/) for job definition examples
- Read [CONTRIBUTING.md](CONTRIBUTING.md) to contribute
