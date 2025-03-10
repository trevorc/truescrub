workspace(name = "truescrub")

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

# Python setup
http_archive(
    name = "rules_python",
    sha256 = "8c15896f6686beb5c631a4459a3aa8392daccaab805ea899c9d14215074b60ef",
    strip_prefix = "rules_python-0.17.3",
    url = "https://github.com/bazelbuild/rules_python/archive/refs/tags/0.17.3.tar.gz",
)

load("@rules_python//python:repositories.bzl", "py_repositories", "python_register_toolchains")
py_repositories()

python_register_toolchains(
    name = "python3",
    python_version = "3.11",
)

# Pip dependencies are managed by scripts/setup_bazel.sh
# The script will add a new_local_repository entry for pip_deps

# Protocol Buffers setup (continued below with COM_GOOGLE_PROTOBUF var for readability)
COM_GOOGLE_PROTOBUF = "com_google_protobuf"

# Protocol Buffers setup
http_archive(
    name = COM_GOOGLE_PROTOBUF,
    sha256 = "75be42bd736f4df6d702a0e4e4d30de9ee40eac024c4b845d17ae4cc831fe4ae",
    strip_prefix = "protobuf-21.7",
    urls = ["https://github.com/protocolbuffers/protobuf/archive/v21.7.tar.gz"],
)

load("@com_google_protobuf//:protobuf_deps.bzl", "protobuf_deps")
protobuf_deps()

# Skylib setup
http_archive(
    name = "bazel_skylib",
    sha256 = "74d544d96f4a5bb630d465ca8bbcfe231e3594e5aae57e1edbf17a6eb3ca2506",
    urls = [
        "https://mirror.bazel.build/github.com/bazelbuild/bazel-skylib/releases/download/1.3.0/bazel-skylib-1.3.0.tar.gz",
        "https://github.com/bazelbuild/bazel-skylib/releases/download/1.3.0/bazel-skylib-1.3.0.tar.gz",
    ],
)

load("@bazel_skylib//:workspace.bzl", "bazel_skylib_workspace")
bazel_skylib_workspace()

# Site packages repository (managed by setup_bazel.sh)
new_local_repository(
    name = "pip_deps",
    build_file = "//:pip_deps.BUILD",
    path = "/Users/wilson/.pyenv/versions/truescrub/lib/python3.11/site-packages",
)
