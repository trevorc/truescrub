load("@rules_python//python:defs.bzl", "py_binary")
load("@pip_requirements//:requirements.bzl", "requirement")
load("@bazel_tools//tools/build_defs/pkg:pkg.bzl", "pkg_tar")

py_library(
    name = "models",
    srcs = ["models.py"],
    visibility = [
        "//tests:__pkg__",
        "//truescrub/updater:__pkg__",
    ],
    deps = [
        requirement("trueskill"),
    ],
)

py_library(
    name = "matchmaking",
    srcs = ["matchmaking.py"],
    visibility = ["//truescrub/updater:__pkg__"],
    deps = [
        ":models",
        requirement("trueskill"),
    ],
)

py_library(
    name = "db",
    srcs = ["db.py"],
    visibility = ["//truescrub/updater:__pkg__"],
    deps = [
        ":models",
        requirement("trueskill"),
    ],
)

py_library(
    name = "state_serialization",
    srcs = ["state_serialization.py"],
    visibility = ["//tests:__pkg__"],
    deps = [
        ":models",
        "//truescrub/proto:game_state_py_proto",
    ],
)

py_binary(
    name = "teameval",
    srcs = [
        "teameval.py",
    ],
    deps = [
        ":db",
        ":matchmaking",
        ":models",
    ],
)

py_library(
    name = "api",
    srcs = [
        "__init__.py",
        "api.py",
        "highlights.py",
    ],
    data = [
        "htdocs/vendor/highcharts-8.0.0.js",
        "htdocs/vendor/highcharts-more-8.0.0.js",
        "templates/index.html",
        "templates/leaderboard.html",
        "templates/macros.html",
        "templates/matchmaking.html",
        "templates/profile.html",
        "templates/skill_groups.html",
    ],
    deps = [
        ":db",
        ":matchmaking",
        ":models",
        "//truescrub/updater",
        requirement("Flask"),
        requirement("waitress"),
    ],
)

py_binary(
    name = "truescrub",
    srcs = ["__main__.py"],
    main = "__main__.py",
    srcs_version = "PY3",
    deps = [":api"],
)
