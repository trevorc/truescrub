load("@aspect_rules_py//py:defs.bzl", "py_binary", "py_library")

py_library(
    name = "teameval_lib",
    srcs = ["teameval.py"],
    visibility = [
        "//:__pkg__",
        "//tests:__pkg__",
    ],
    deps = [
        "//truescrub:db",
        "//truescrub:matchmaking",
        "//truescrub:models",
    ],
)

py_binary(
    name = "teameval",
    main = "teameval.py",
    visibility = [
        "//:__pkg__",
        "//tests:__pkg__",
    ],
    deps = [":teameval_lib"],
)

py_binary(
    name = "genetic",
    srcs = ["genetic.py"],
    deps = [
        "//truescrub:db",
        "//truescrub:models",
        "//truescrub/tools:teameval_lib",
        "@pypi//deap",
    ],
)

py_binary(
    name = "optuna_match",
    srcs = ["optuna_match.py"],
    deps = [
        "//truescrub:db",
        "//truescrub:models",
        "//truescrub/tools:genetic",
        "//truescrub/tools:teameval_lib",
        "@pypi//optuna",
    ],
)

py_binary(
    name = "log_translator",
    srcs = ["log_translator.py"],
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
        "@pypi//tqdm",
    ],
)

py_binary(
    name = "logquery",
    srcs = ["logquery.py"],
    deps = [
        "//truescrub/statewriter",
        "@pypi//tqdm",
    ],
)

py_binary(
    name = "surgery",
    srcs = ["surgery.py"],
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
    deps = [
        "//truescrub:accolades",
        "//truescrub:highlights",
    ],
)

py_binary(
    name = "recover_log",
    srcs = ["recover_log.py"],
    deps = [
        "//truescrub:envconfig",
        "//truescrub/proto:game_state_py_pb2",
        "//truescrub/statewriter:segmented_log",
    ],
)

py_binary(
    name = "compact_log",
    srcs = ["compact_log.py"],
    deps = [
        "//truescrub:envconfig",
        "//truescrub/proto:game_state_py_pb2",
        "//truescrub/statewriter:segmented_log",
        "@pypi//tqdm",
    ],
)
