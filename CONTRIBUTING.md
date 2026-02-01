# Contributing to Plan-Z CLI

Thank you for your interest in contributing to Plan-Z CLI! This document provides guidelines and information for contributors.

## Development Setup

### Prerequisites

- Python 3.9 or higher
- pip

### Setting Up the Development Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/LuckyPrayer/plan-z.git
   cd plan-z/plan-z\ cli
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Code Style

We use the following tools to maintain code quality:

- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking

Run all checks:
```bash
black src tests
ruff check src tests
mypy src
```

## Running Tests

```bash
pytest
```

With coverage:
```bash
pytest --cov=planz --cov-report=html
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and code quality checks
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Commit Messages

Follow conventional commits:
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `test:` Test additions/changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

## Reporting Issues

When reporting issues, please include:
- CronCTL version
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
