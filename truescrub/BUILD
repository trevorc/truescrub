load("@aspect_rules_py//py:defs.bzl", "py_binary", "py_image_layer", "py_layer_tier", "py_library")
load("@bazel_lib//lib:transitions.bzl", "platform_transition_filegroup")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_pkg//pkg:tar.bzl", "pkg_tar")

package(
    default_visibility = [
        "//tests:__pkg__",
        "//truescrub/statewriter:__pkg__",
        "//truescrub/tools:__pkg__",
        "//truescrub/updater:__pkg__",
    ],
)

py_library(
    name = "envconfig",
    srcs = ["envconfig.py"],
    visibility = ["//truescrub:__subpackages__"],
)

py_library(
    name = "seasoncfg",
    srcs = ["seasoncfg.py"],
    deps = [":envconfig"],
)

py_library(
    name = "models",
    srcs = ["models.py"],
    data = ["//truescrub/proto:skill_groups.json"],
    deps = [
        "//proto:common_py_pb2",
        "//truescrub/proto:profile_py_pb2",
        "@pypi//trueskill",
    ],
)

py_library(
    name = "matchmaking",
    srcs = ["matchmaking.py"],
    deps = [
        ":models",
        "@pypi//trueskill",
    ],
)

py_library(
    name = "db",
    srcs = ["db.py"],
    deps = [
        ":envconfig",
        ":models",
        "@pypi//trueskill",
    ],
)

py_library(
    name = "queue_consumer",
    srcs = ["queue_consumer.py"],
)

py_library(
    name = "highlights",
    srcs = ["highlights.py"],
    deps = [
        ":accolades",
        ":db",
        ":models",
        "//proto:common_py_pb2",
        "//proto:highlights_service_py_pb2_grpc",
    ],
)

py_library(
    name = "accolades",
    srcs = ["accolades.py"],
    data = ["accolades.ini"],
    visibility = [
        "//tests:__pkg__",
        "//truescrub/tools:__pkg__",
    ],
    deps = [
        ":db",
        ":models",
        "//proto:common_py_pb2",
        "//proto:highlights_service_py_pb2_grpc",
    ],
)

py_library(
    name = "achievements",
    srcs = ["achievements.py"],
    data = ["//truescrub/proto:achievements.json"],
    visibility = ["//tests:__pkg__"],
    deps = [
        ":db",
        "//truescrub/proto:profile_py_pb2",
    ],
)

py_library(
    name = "rpc",
    srcs = ["rpc.py"],
    deps = [
        ":achievements",
        ":db",
        ":highlights",
        ":interceptors",
        ":matchmaking",
        ":models",
        "//proto:common_py_pb2",
        "//proto:highlights_service_py_pb2_grpc",
        "//proto:leaderboard_service_py_pb2_grpc",
        "//proto:matchmaking_service_py_pb2_grpc",
        "//proto:profile_service_py_pb2_grpc",
        "//proto:season_service_py_pb2_grpc",
        "@pypi//grpcio",
    ],
)

py_library(
    name = "application",
    srcs = [
        "__init__.py",
        "application.py",
    ],
    deps = [
        ":db",
        ":interceptors",
        ":queue_consumer",
        ":rpc",
        "//proto:highlights_service_py_pb2_grpc",
        "//proto:leaderboard_service_py_pb2_grpc",
        "//proto:matchmaking_service_py_pb2_grpc",
        "//proto:profile_service_py_pb2_grpc",
        "//proto:season_service_py_pb2_grpc",
        "//truescrub/proto:game_state_py_pb2",
        "//truescrub/statewriter",
        "//truescrub/updater",
        "@pypi//grpcio",
        "@pypi//grpcio_health_checking",
        "@pypi//grpcio_reflection",
    ],
)

py_binary(
    name = "truescrub",
    srcs = ["__main__.py"],
    main = "__main__.py",
    visibility = [
        "//:__pkg__",
    ],
    deps = [":application"],
)

py_library(
    name = "interceptors",
    srcs = ["interceptors.py"],
    deps = [
        ":db",
        "@pypi//grpcio",
    ],
)

py_layer_tier(
    name = "tier",
    interpreter_group = "interpreter",
)

pkg_tar(
    name = "data_dir",
    empty_dirs = ["/data"],
    mode = "0755",
    owner = "65532.65532",
)

py_image_layer(
    name = "layer",
    binary = ":truescrub",
    layer_tier = ":tier",
)

platform(
    name = "linux_amd64",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:x86_64",
    ],
)

platform_transition_filegroup(
    name = "layer_amd64",
    srcs = [":layer"],
    target_platform = ":linux_amd64",
)

platform(
    name = "linux_arm64",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:aarch64",
    ],
)

platform_transition_filegroup(
    name = "layer_arm64",
    srcs = [":layer"],
    target_platform = ":linux_arm64",
)

ENTRYPOINT = [
    "/app.runfiles/_main/truescrub/._truescrub.venv/bin/python3",
    "/app.runfiles/_main/truescrub/__main__.py",
    "--addr=0.0.0.0",
    "--port=9000",
]

oci_image(
    name = "image_amd64",
    base = "@distroless_cc_linux_amd64",
    entrypoint = ENTRYPOINT,
    env = {
        "TRUESCRUB_DATA_DIR": "/data",
        "PYTHONPATH": "/app.runfiles/_main",
        "LD_LIBRARY_PATH": "/app.runfiles/aspect_rules_py++python_interpreters+python_3_12_x86_64_unknown_linux_gnu/lib:/app.runfiles/_main/_solib_k8/_U_A_Arules_Upython++python+python_U3_U12_Ux86_U64-unknown-linux-gnu_S_S_Clibpython___Ulib",
    },
    exposed_ports = ["9000/tcp"],
    tars = [
        ":data_dir",
        ":layer_amd64",
    ],
    user = "65532",
    workdir = "/app.runfiles/_main",
)

oci_image(
    name = "image_arm64",
    base = "@distroless_cc_linux_arm64_v8",
    entrypoint = ENTRYPOINT,
    env = {
        "TRUESCRUB_DATA_DIR": "/data",
        "PYTHONPATH": "/app.runfiles/_main",
        "LD_LIBRARY_PATH": "/app.runfiles/aspect_rules_py++python_interpreters+python_3_12_aarch64_unknown_linux_gnu/lib:/app.runfiles/_main/_solib_k8/_U_A_Arules_Upython++python+python_U3_U12_Uaarch64-unknown-linux-gnu_S_S_Clibpython___Ulib",
    },
    exposed_ports = ["9000/tcp"],
    tars = [
        ":data_dir",
        ":layer_arm64",
    ],
    user = "65532",
    workdir = "/app.runfiles/_main",
)

oci_image_index(
    name = "image_index",
    images = [
        ":image_amd64",
        ":image_arm64",
    ],
)

oci_push(
    name = "push",
    image = ":image_index",
    remote_tags = ["latest"],
    repository = "localhost:5000/truescrub",
)

oci_load(
    name = "load_amd64",
    image = ":image_amd64",
    repo_tags = ["truescrub:latest"],
)
