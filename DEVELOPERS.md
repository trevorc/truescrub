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

1. Install Bazel 8.1.1: https://bazel.build/install
2. Set up Python environment (recommended):
   ```bash
   pyenv install 3.11.11
   pyenv virtualenv 3.11.11 truescrub
   pyenv activate truescrub
   ```
3. Set up the project:
   ```bash
   make setup      # Install runtime dependencies
   make setup-dev  # Install development dependencies
   make protos     # Generate protobuf files
   ```

## Bazel Configuration

The project uses Bazel 8.1.1 for building and testing, with a platform-specific configuration setup by `scripts/setup_bazel.sh`. This script automatically:

- Detects the operating system (macOS/Linux)
- Configures the macOS SDK version from Xcode (on macOS)
- Sets up the Python site-packages path for dependencies

The `bazel-setup` Make target runs this script and is included as a dependency for all build and test targets.