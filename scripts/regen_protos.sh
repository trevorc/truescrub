#!/bin/bash

set -e

# Make sure we're in the repository root
cd "$(dirname "$0")/.."

# Check if mypy-protobuf is installed
if ! pip show mypy-protobuf &> /dev/null; then
    echo "mypy-protobuf is not installed. Installing it now..."
    pip install mypy-protobuf
fi

# Locate the protoc-gen-mypy plugin
MYPY_PLUGIN=$(which protoc-gen-mypy 2>/dev/null || echo "")
if [ -z "$MYPY_PLUGIN" ]; then
    echo "Could not find protoc-gen-mypy. Make sure mypy-protobuf is installed correctly."
    exit 1
fi

# Generate protobuf Python files and type stubs
echo "Generating protobuf files and type stubs..."
protoc --python_out=. --mypy_out=. truescrub/proto/game_state.proto

# Check if both files were generated
if [ -f "truescrub/proto/game_state_pb2.py" ] && [ -f "truescrub/proto/game_state_pb2.pyi" ]; then
    echo "Protobuf files and type stubs generated successfully."
else
    echo "Error: Failed to generate one or more files."
    exit 1
fi