#!/bin/bash

set -e

# Make sure we're in the repository root
cd "$(dirname "$0")/.."

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