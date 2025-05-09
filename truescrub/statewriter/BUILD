load("@rules_python//python:defs.bzl", "py_library")

package(default_visibility = [
    "//tests:__pkg__",
    "//truescrub:__pkg__",
    "//truescrub/tools:__pkg__",
])

py_library(
    name = "state_serialization",
    srcs = ["state_serialization.py"],
    deps = [
        "//truescrub:models",
        "//truescrub/proto:game_state_py_pb2",
    ],
)

py_library(
    name = "game_state_log",
    srcs = ["game_state_log.py"],
    deps = [
        "//truescrub/proto:game_state_py_pb2",
        "@riegeli//python/riegeli",
    ],
)

py_library(
    name = "statewriter",
    srcs = [
        "__init__.py",
        "state_writer.py",
    ],
    deps = [
        ":game_state_log",
        ":state_serialization",
        "//truescrub:db",
        "//truescrub:queue_consumer",
        "//truescrub/proto:game_state_py_pb2",
        "@riegeli//python/riegeli",
    ],
)
