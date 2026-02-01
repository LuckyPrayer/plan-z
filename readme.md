# Plan-Z CLI – Cross-Platform Distributed Job Scheduler

> **Part of the [Plan-Z Project](https://github.com/LuckyPrayer/plan-z)** – This is the backend CLI component. See also: [Plan-Z Client](../plan-z%20client) (web interface)

A command‑line tool for managing scheduled jobs on **local and remote hosts** across **Windows, Linux, macOS, and Docker** from a single interface. Plan-Z CLI provides structure, visibility, and safety on top of traditional schedulers.

Think of it as:

* Cron + Task Scheduler, unified and inspectable
* Ansible-lite for scheduled jobs
* Cross-platform job orchestration without complexity
* A stepping stone toward a full scheduler platform

---

## ✨ Goals

* Manage scheduled jobs from a single CLI
* **Cross-platform**: Windows (Task Scheduler), Linux/macOS (cron), Docker
* Support local and remote hosts on different operating systems
* Avoid manual crontab/Task Scheduler editing
* Provide consistent execution, logging, and history across platforms
* Be automation‑friendly and scriptable
* Remain usable over SSH, CI, and air‑gapped systems

---

## 🔑 Core Concepts

### Hosts

A *host* is any system where jobs may run:

* Local machine (auto-detects Windows/Unix)
* Remote Linux/macOS host over SSH
* Remote Windows host over SSH (OpenSSH) or WinRM
* Docker containers (local or remote)

### Jobs

A *job* is a managed scheduled entry with metadata, logging, and lifecycle controls.
Jobs use cron syntax internally but are translated to native scheduler formats.

### Controller Model

```
[ planz CLI ]
        |
        v
[ Local Controller ] ── SSH ──► [ Remote Controller ]
        |                              |
        v                              v
  ┌─────────────┐              ┌─────────────┐
  │ Windows:    │              │ Linux/Mac:  │
  │ Task Sched. │              │ cron        │
  │─────────────│              │─────────────│
  │ Linux/Mac:  │              │ Docker:     │
  │ cron        │              │ containers  │
  └─────────────┘              └─────────────┘
```

Each host runs a lightweight **controller** responsible for:

* Installing scheduler entries (cron or Task Scheduler)
* Executing commands safely with platform-appropriate shells
* Capturing logs and status

---

## 🔧 Core Features

### Job Management

* Create, update, delete jobs
* Enable / disable jobs
* Run jobs immediately (`planz run`)
* Group jobs by tags (e.g. `backup`, `etl`)

### Supported Job Types

* Shell commands (PowerShell, Bash, cmd, sh)
* Script execution (bash, python, PowerShell, etc.)
* HTTP requests (webhooks)
* **Docker container execution**

### Execution Modes

| Mode     | Description                                      |
| -------- | ------------------------------------------------ |
| Native   | Uses host's scheduler (cron/Task Scheduler)      |
| Docker   | Runs job in a Docker container                   |
| Shell    | Direct execution for manual/ad-hoc runs          |

---

### Scheduling

Supports multiple schedule formats (translated per platform):

| Type     | Example          | Windows               | Unix                 |
| -------- | ---------------- | --------------------- | -------------------- |
| Cron     | `0 2 * * *`      | Task Scheduler daily  | crontab entry        |
| Interval | Every 10 minutes | /SC MINUTE /MO 10     | */10 * * * *         |
| Calendar | Mondays at 08:00 | /SC WEEKLY /D MON     | 0 8 * * 1            |
| One‑shot | Run once         | One-time task         | at command           |

Schedules are normalized internally to avoid lock‑in to raw crontab syntax.

---

### Execution Controls

* Per-job timeouts
* Retry policies
* Overlap control (allow / forbid concurrent runs)
* Environment variables per job
* Working directory

---

### Observability

* Execution history
* Exit codes
* Start / end timestamps
* Stdout / stderr capture
* Clear statuses:

  * ✅ Success
  * ❌ Failed
  * ⏱ Timeout
  * ⛔ Killed

Optional:

* Log rotation
* Structured JSON logs

---

### Notifications (Optional)

* Email
* Slack / Discord webhooks
* Trigger on failure or success

---

## 🧱 Architecture

### Local Mode

```
planz CLI
   |
   v
Platform Detector
   |
   ├── Windows ──► Task Scheduler
   ├── Linux/Mac ──► cron
   └── Docker ──► Container
```

### Remote Mode

```
planz CLI
   |
   └── SSH ──► Remote Host
                  |
                  ├── Windows ──► Task Scheduler
                  ├── Linux/Mac ──► cron
                  └── Docker ──► Container
```

### Cross-Platform Job Execution

```yaml
# Example: Same job, different platforms
name: backup-database
schedule: "0 2 * * *"
command: ./backup.sh              # Default (Unix)
command_windows: backup.ps1       # Override for Windows
docker_image: postgres:15         # Or run in Docker
```

The controller is intentionally simple and stateless where possible.

---

## 🛠 Technology Choices

### CLI

* Language: **Python**
* Config format: YAML
* Output: human-readable + JSON (`--json`)

### Remote Communication

* SSH (Linux, macOS, Windows with OpenSSH)
* Key-based authentication only
* No persistent agent required (MVP)

### Storage

* Job definitions stored locally (files)
* Installed cron entries annotated with identifiers
* Logs stored per-host

---

## 🗃 Job Definition Format

Example job file:

```yaml
name: nightly-backup
host: db01
schedule: "0 2 * * *"
command: /usr/local/bin/backup.sh
timeout: 3600
env:
  BACKUP_TARGET: s3
notify:
  on_failure: slack
```

---

## ⚙ Execution Model

### Installation

* `planz apply` renders job definitions
* Installs annotated cron entries
* Maintains idempotency

### Execution

* Cron invokes controller wrapper
* Wrapper executes job
* Captures output and exit code
* Writes logs and metadata

---

## 🔐 Security Model

* Never runs jobs as root
* SSH key‑based access only
* Explicit host allowlists
* Secrets masked in logs
* Optional secret injection via env vars

---

## 🚀 MVP Roadmap

### Phase 1 – Local Control

* CLI scaffold
* Job definition files
* Local cron install/remove
* Manual run support

### Phase 2 – Remote Hosts

* SSH execution
* Remote cron management
* Log retrieval

### Phase 3 – Visibility

* Job status listing
* Execution history
* Notifications

---

## 🌱 Future Enhancements

* Agent-based execution
* Git-backed job repositories
* Job templates
* RBAC
* Web UI wrapper
* Docker container

---

## 🤝 Contributing

Plan-Z is designed to grow incrementally. Contributions and design discussions are welcome once the CLI MVP stabilizes.

---

## 📜 License

TBD (MIT or Apache-2.0 recommended)
