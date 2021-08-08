load("@rules_python//python:defs.bzl", "py_test")
load("@pip_requirements//:requirements.bzl", "requirement")

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
        "//truescrub:state_serialization",
        requirement("pytest"),
    ],
)

test_suite(
    name = "tests",
    tests = [
        "test_matchmaking",
        "test_models",
        "test_state_serialization",
    ],
)
