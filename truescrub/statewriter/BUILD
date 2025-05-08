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
    name = "statewriter",
    srcs = [
        "__init__.py",
        "state_writer.py",
    ],
    deps = [
        "//truescrub:db",
        "//truescrub:queue_consumer",
    ],
)
