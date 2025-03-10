# TrueScrub

TrueScrub is a rating system for games that uses TrueSkill for skill-based matchmaking.

## Development Setup

### Prerequisites

- Python 3.11+
- Protobuf compiler (protoc)
- Bazel (optional)

### Python Environment Setup

To set up the Python development environment, run:

```bash
make setup
```

This will:
1. Create a virtual environment
2. Install all required dependencies
3. Generate necessary protobuf files

### Running Tests

To run tests:

```bash
make test
```

### Running the Application

To run the application locally:

```bash
make serve
```

The application will be available at http://localhost:3000.

### Development Commands

- `make regen-protos` - Regenerate protobuf files
- `make test` - Run tests
- `make serve` - Start the local development server

## Bazel Support

The project is built using Bazel 8.1.1. The `setup_bazel.sh` script configures Bazel to work with your Python environment:

```bash
# Set up Bazel with dependencies from your virtualenv
./scripts/setup_bazel.sh

# Build the application
bazel build //truescrub

# Run tests
bazel test //tests:tests
```

### How Bazel Integration Works

The Bazel integration provides a clean approach to Python dependencies:

1. Uses Bzlmod for modern dependency management
2. Creates a dummy `pip_deps` repository structure with empty BUILD files
3. Sets `PYTHONPATH` in the Bazel environment to access your system Python packages at runtime
4. Ensures all tests and builds can find required dependencies

This approach offers several advantages:
- No need to vendor third-party dependencies
- Works with your existing Python environment
- Simple setup that doesn't require complex Bazel rules
- Avoids dependency version conflicts
- Works consistently across platforms

## Deployment

To build and deploy the application:

```bash
make deploy
```

This will build the application with Bazel and deploy it to the host specified in the Makefile.