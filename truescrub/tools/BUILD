load("@pip_requirements//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_binary")

py_binary(
    name = "teameval",
    srcs = [
        "teameval.py",
    ],
    legacy_create_init = False,
    deps = [
        "//truescrub:db",
        "//truescrub:matchmaking",
        "//truescrub:models",
    ],
)

py_binary(
    name = "genetic",
    srcs = ["genetic.py"],
    legacy_create_init = False,
    deps = [
        "//truescrub:db",
        "//truescrub:models",
        "//truescrub/tools:teameval",
        requirement("deap"),
    ],
)



py_binary(
    name = "log_translator",
    srcs = ["log_translator.py"],
    legacy_create_init = False,
    visibility = [
        "//:__pkg__",
        "//tests:__pkg__",
    ],
    deps = [
        "//truescrub:db",
        "//truescrub/proto:game_state_py_pb2",
        "//truescrub/statewriter",
        "//truescrub/statewriter:state_parsing",
        "//truescrub/statewriter:state_serialization",
        requirement("tqdm"),
    ],
)

py_binary(
    name = "logquery",
    srcs = ["logquery.py"],
    legacy_create_init = False,
    deps = [
        "//truescrub/statewriter",
        requirement("tqdm"),
    ],
)

py_binary(
    name = "surgery",
    srcs = ["surgery.py"],
    legacy_create_init = False,
    main = "surgery.py",
    visibility = [
        "//:__pkg__",
        "//tests:__pkg__",
    ],
    deps = [
        "//truescrub:db",
        "//truescrub/proto:game_state_py_pb2",
        "//truescrub/statewriter",
        "//truescrub/statewriter:state_parsing",
    ],
)

py_binary(
    name = "printaccolades",
    srcs = ["printaccolades.py"],
    legacy_create_init = False,
    deps = [
        "//truescrub:accolades",
        "//truescrub:highlights",
    ],
)
