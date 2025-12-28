load("@pip_requirements//:requirements.bzl", "requirement")

py_library(
    name = "state_parser",
    srcs = ["state_parser.py"],
    deps = ["//truescrub:models"],
)

py_library(
    name = "remapper",
    srcs = ["remapper.py"],
    data = ["players.ini"],
)

py_library(
    name = "recalculate",
    srcs = ["recalculate.py"],
    deps = [
        ":remapper",
        ":state_parser",
        "//truescrub:db",
        "//truescrub:models",
        "//truescrub:seasoncfg",
    ],
)

py_library(
    name = "evaluator",
    srcs = ["evaluator.py"],
    deps = [
        ":recalculate",
        "//truescrub:db",
        "//truescrub:matchmaking",
        "//truescrub:models",
    ],
)

py_library(
    name = "updater",
    srcs = [
        "__init__.py",
        "updater.py",
    ],
    visibility = [
        "//tests:__pkg__",
        "//truescrub:__pkg__",
    ],
    deps = [
        ":evaluator",
        ":recalculate",
        "//truescrub:db",
        "//truescrub:queue_consumer",
    ],
)

py_binary(
    name = "updater_main",
    srcs = ["__main__.py"],
    main = "__main__.py",
    deps = [
        ":evaluator",
        ":updater",
    ],
)
