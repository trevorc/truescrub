# TrueScrub Development Guide

## Build Commands

- `make build` - Build the project
- `make test` - Run tests
- `make serve` - Run the server locally

## Code Quality Tools

The project uses several code quality tools that can be run using Make:

- `make lint` - Run ruff linter to check code
- `make lint-fix` - Run ruff linter and fix issues automatically 
- `make format` - Run black and isort formatters
- `make typecheck` - Run mypy type checker
- `make quality` - Run both linting and type checking

## Development Setup

To set up the development environment:

1. Install Bazel: https://bazel.build/install
2. Set up Python environment: `pyenv install 3.11.11` and `pyenv virtualenv 3.11.11 truescrub`
3. Activate the environment: `pyenv activate truescrub`
4. Install dependencies: `pip install -r requirements.in`
5. Install dev tools: `pip install -r requirements-dev.in`

## Bazel Configuration

The project uses Bazel for building and testing, with a platform-specific configuration setup by `scripts/setup_bazel.sh`. This script automatically detects:

- The operating system (macOS/Linux)
- The macOS SDK version from Xcode (for macOS platforms)
- The Python site-packages path

To ensure Bazel is properly configured before building or testing, the `bazel-setup` target should always be run first.