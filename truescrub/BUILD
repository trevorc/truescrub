load("@aspect_rules_py//py:defs.bzl", "py_binary", "py_image_layer", "py_layer_tier", "py_library")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@tar.bzl", "tar")

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
    visibility = [
        "//tests:__pkg__",
        "//truescrub:__subpackages__",
    ],
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
        "//proto:config_service_py_pb2_grpc",
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
        "//proto:config_service_py_pb2_grpc",
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
    visibility = ["//:__pkg__"],
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
    groups = {
        "@@riegeli+//python/riegeli/records:record_writer": "40_riegeli",
        "@@riegeli+//python/riegeli/records:record_reader": "40_riegeli",
    },
    interpreter_group = "10_interpreter",
)

tar(
    name = "data_dir",
    mtree = ["data type=dir uid=65532 gid=65532 mode=0755"],
)

py_image_layer(
    name = "layer",
    binary = ":truescrub",
    layer_tier = ":tier",
)

oci_image(
    name = "image",
    base = "@distroless_cc",
    entrypoint = ["/app"],
    env = {"TRUESCRUB_DATA_DIR": "/data"},
    exposed_ports = ["9000/tcp"],
    tars = [
        ":data_dir",
        ":layer",
    ],
    user = "65532",
    workdir = "/app.runfiles/_main",
)

oci_image_index(
    name = "image_index",
    images = [":image"],
    platforms = [
        "//platform:linux_amd64",
        "//platform:linux_arm64",
    ],
)

oci_push(
    name = "push",
    image = ":image_index",
)
