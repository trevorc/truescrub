#!/bin/bash

set -e

# Make sure we're in the repository root
cd "$(dirname "$0")/.."

# Create the Python virtual environment if it doesn't exist
if [ ! -d .venv ]; then
  echo "Creating Python virtual environment..."
  python -m venv .venv
fi

# Activate the virtual environment
source .venv/bin/activate

# Install the required packages
echo "Installing required packages..."
pip install -r requirements.in

# Generate protobuf Python files if they don't exist
if [ ! -f truescrub/proto/game_state_pb2.py ]; then
  echo "Generating protobuf files..."
  protoc --python_out=. truescrub/proto/game_state.proto
fi

echo ""
echo "Development environment set up successfully!"
echo ""
echo "To activate the environment, run:"
echo "  source .venv/bin/activate"
echo ""
echo "To deactivate the environment, run:"
echo "  deactivate"
echo ""
echo "To run tests, execute:"
echo "  python -m pytest"
echo ""
echo "To run the application, execute:"
echo "  TRUESCRUB_DATA_DIR=./data python -m truescrub"
echo ""