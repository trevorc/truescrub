load("@bazel_tools//tools/python:toolchain.bzl", "py_runtime_pair")
load("@rules_python//python:pip.bzl", "compile_pip_requirements")

compile_pip_requirements(
    name = "requirements",
    requirements_in = "requirements.in",
    requirements_txt = "requirements_lock.txt",
)

py_runtime(
    name = "hermetic_python3",
    files = [],
    interpreter = "//scripts:python_binary",
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

filegroup(
    name = "truescrub_zip",
    srcs = ["//truescrub"],
    output_group = "python_zip_file",
    visibility = ["//:__pkg__"],
)

filegroup(
    name = "dbsurgery_zip",
    srcs = ["//truescrub/tools:dbsurgery"],
    output_group = "python_zip_file",
)
