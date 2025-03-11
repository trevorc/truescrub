#!/bin/bash

set -e

# Make sure we're in the repository root
cd "$(dirname "$0")/.."

# Determine the platform and create platform configuration
PLATFORM=$(uname -s)
echo "# Generated file - DO NOT EDIT" > .bazelrc.local

# Add platform-specific settings
if [[ "$PLATFORM" == "Darwin" ]]; then
    # Get SDK version from Xcode
    SDK_VERSION=$(xcrun --show-sdk-version | cut -d. -f1,2)
    echo "# macOS-specific settings" >> .bazelrc.local
    echo "build --macos_sdk_version=${SDK_VERSION}" >> .bazelrc.local
    echo "test --macos_sdk_version=${SDK_VERSION}" >> .bazelrc.local
    echo "run --macos_sdk_version=${SDK_VERSION}" >> .bazelrc.local
    echo "Platform detected: macOS with SDK version ${SDK_VERSION}"
elif [[ "$PLATFORM" == "Linux" ]]; then
    # Detect CPU architecture
    CPU_ARCH=$(uname -m)
    echo "# Linux-specific settings for $CPU_ARCH" >> .bazelrc.local
    echo "Platform detected: Linux on $CPU_ARCH"
else
    echo "# Unknown platform settings" >> .bazelrc.local
    echo "Platform detected: ${PLATFORM} (no specific configuration)"
fi

# Add PYTHONPATH environment variable to Bazel config
PYTHON_SITE_PACKAGES=$(python -c 'import site; print(site.getsitepackages()[0])')
echo "" >> .bazelrc.local
echo "# Set PYTHONPATH for all actions" >> .bazelrc.local
echo "build --action_env PYTHONPATH=${PYTHON_SITE_PACKAGES}" >> .bazelrc.local
echo "test --action_env PYTHONPATH=${PYTHON_SITE_PACKAGES}" >> .bazelrc.local
echo "run --action_env PYTHONPATH=${PYTHON_SITE_PACKAGES}" >> .bazelrc.local
echo "Using Python site-packages from: ${PYTHON_SITE_PACKAGES}"

echo "Bazel configuration updated successfully."