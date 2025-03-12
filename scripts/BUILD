load("@rules_python//python:defs.bzl", "py_runtime_pair")

filegroup(
    name = "python_binary",
    srcs = ["python.sh"],
    visibility = ["//:__pkg__"],
)

py_runtime(
    name = "hermetic_python3",
    files = [],
    interpreter = ":python_binary",
    python_version = "PY3",
)

py_runtime_pair(
    name = "hermetic_python_runtime",
    py3_runtime = ":hermetic_python3",
)

toolchain(
    name = "hermetic_python_toolchain",
    toolchain = ":hermetic_python_runtime",
    toolchain_type = "@bazel_tools//tools/python:toolchain_type",
)
