load("@aspect_rules_py//py:defs.bzl", "py_binary", "py_library")

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
    deps = [
        "//proto:common_py_pb2",
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
    visibility = ["//tests:__pkg__"],
    deps = [":db"],
)

py_library(
    name = "api",
    srcs = [
        "__init__.py",
        "api.py",
        "highlights.py",
    ],
    data = [
        "templates/layout.html",
        "templates/macros.html",
        "templates/profile.html",
        "templates/skill_groups.html",
    ],
    deps = [
        ":accolades",
        ":achievements",
        ":db",
        ":highlights",
        ":matchmaking",
        ":models",
        "@pypi//flask",
        "@pypi//waitress",
    ],
)

py_library(
    name = "rpc",
    srcs = ["rpc.py"],
    deps = [
        ":api",
        ":db",
        ":interceptors",
        "//proto:common_py_pb2",
        "//proto:highlights_service_py_pb2_grpc",
        "//proto:leaderboard_service_py_pb2_grpc",
        "//proto:matchmaking_service_py_pb2_grpc",
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
        ":api",
        ":db",
        ":interceptors",
        ":queue_consumer",
        ":rpc",
        "//proto:highlights_service_py_pb2_grpc",
        "//proto:leaderboard_service_py_pb2_grpc",
        "//proto:matchmaking_service_py_pb2_grpc",
        "//proto:season_service_py_pb2_grpc",
        "//truescrub/proto:game_state_py_pb2",
        "//truescrub/statewriter",
        "//truescrub/updater",
        "@pypi//grpcio",
        "@pypi//grpcio_health_checking",
        "@pypi//grpcio_reflection",
        "@pypi//sonora",
    ],
)

py_binary(
    name = "truescrub",
    srcs = ["__main__.py"],
    main = "__main__.py",
    visibility = [
        "//:__pkg__",
        "//container:__pkg__",
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
