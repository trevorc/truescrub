load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")
load("@bazel_tools//tools/build_defs/repo:git.bzl", "git_repository")

### Python

http_archive(
    name = "rules_python",
    sha256 = "a30abdfc7126d497a7698c29c46ea9901c6392d6ed315171a6df5ce433aa4502",
    strip_prefix = "rules_python-0.6.0",
    url = "https://github.com/bazelbuild/rules_python/archive/0.6.0.tar.gz",
)

load("@rules_python//python:pip.bzl", "pip_install")

pip_install(
    name = "pip_requirements",
    quiet = False,
    requirements = "//:requirements.txt",
)

### Protobuf

http_archive(
    name = "rules_proto",
    sha256 = "66bfdf8782796239d3875d37e7de19b1d94301e8972b3cbd2446b332429b4df1",
    strip_prefix = "rules_proto-4.0.0",
    urls = [
        "https://mirror.bazel.build/github.com/bazelbuild/rules_proto/archive/refs/tags/4.0.0.tar.gz",
        "https://github.com/bazelbuild/rules_proto/archive/refs/tags/4.0.0.tar.gz",
    ],
)

http_archive(
    name = "com_google_protobuf",
    sha256 = "3253c6d17ec0bb6f6382e555cf5ca0a9ffab8d81b691f100f96ce9f5e753018e",
    strip_prefix = "protobuf-3.17.3",
    urls = [
        "https://github.com/protocolbuffers/protobuf/releases/download/v3.17.3/protobuf-python-3.17.3.tar.gz",
    ],
)

load("@rules_proto//proto:repositories.bzl", "rules_proto_dependencies", "rules_proto_toolchains")
load("@com_google_protobuf//:protobuf_deps.bzl", "protobuf_deps")

rules_proto_dependencies()

rules_proto_toolchains()

protobuf_deps()

### Subpar
http_archive(
    name = "subpar",
    sha256 = "b80297a1b8d38027a86836dbadc22f55dc3ecad56728175381aa6330705ac10f",
    strip_prefix = "subpar-2.0.0",
    urls = [
        "https://github.com/google/subpar/archive/refs/tags/2.0.0.tar.gz",
    ],
)
