load("@rules_python//python:defs.bzl", "py_binary")

py_binary(
    name = "teameval",
    srcs = [
        "teameval.py",
    ],
    deps = [
        "//truescrub:db",
        "//truescrub:matchmaking",
        "//truescrub:models",
    ],
)

py_binary(
    name = "gstrans",
    srcs = ["gstrans.py"],
    deps = [
        "//truescrub:db",
        "//truescrub:state_serialization",
    ],
)
