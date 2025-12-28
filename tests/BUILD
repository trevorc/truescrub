load("@pip_requirements//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_library", "py_test")

py_library(
    name = "db_test_utils",
    srcs = [
        "__init__.py",
        "db_test_utils.py",
    ],
    data = ["sample_seasons.toml"],
    deps = [
        "//truescrub:db",
        "//truescrub:models",
        "//truescrub/updater",
    ],
)

py_test(
    name = "test_matchmaking",
    srcs = ["test_matchmaking.py"],
    deps = [
        "//truescrub:matchmaking",
        "//truescrub:models",
        requirement("pytest"),
        requirement("trueskill"),
    ],
)

py_test(
    name = "test_models",
    srcs = ["test_models.py"],
    deps = [
        "//truescrub:models",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_state_serialization",
    srcs = ["test_state_serialization.py"],
    deps = [
        "//truescrub/statewriter:state_serialization",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_game_state_log",
    srcs = ["test_game_state_log.py"],
    deps = [
        requirement("pytest"),
        "//truescrub/statewriter",
        "//truescrub/statewriter:game_state_log",
    ],
)

py_test(
    name = "test_state_writer",
    srcs = ["test_state_writer.py"],
    deps = [
        ":db_test_utils",
        "//truescrub/statewriter",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_highlights",
    srcs = ["test_highlights.py"],
    deps = [
        ":db_test_utils",
        "//truescrub:db",
        "//truescrub:highlights",
        "//truescrub:models",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_accolades",
    srcs = ["test_accolades.py"],
    deps = [
        "//truescrub:accolades",
        requirement("pytest"),
    ],
)

test_suite(
    name = "tests",
    tests = [
        "test_accolades",
        "test_highlights",
        "test_matchmaking",
        "test_models",
        "test_state_serialization",
    ],
)
