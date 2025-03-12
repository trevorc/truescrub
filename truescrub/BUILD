load("@rules_python//python:defs.bzl", "py_binary")
load("@rules_python//python:defs.bzl", "py_library")
load("@pip_requirements//:requirements.bzl", "requirement")

package(
    default_visibility = [
        "//tests:__pkg__",
        "//truescrub/tools:__pkg__",
        "//truescrub/updater:__pkg__",
    ],
)

py_library(
    name = "models",
    srcs = ["models.py"],
    deps = [
        requirement("trueskill"),
    ],
)

py_library(
    name = "matchmaking",
    srcs = ["matchmaking.py"],
    deps = [
        ":models",
        requirement("trueskill"),
    ],
)

py_library(
    name = "db",
    srcs = ["db.py"],
    deps = [
        ":models",
        requirement("trueskill"),
    ],
)

py_library(
    name = "state_serialization",
    srcs = ["state_serialization.py"],
    deps = [
        ":models",
        "//truescrub/proto:game_state_py_pb2",
    ],
)

py_library(
    name = "queue_consumer",
    srcs = ["queue_consumer.py"],
    deps = [],
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
        requirement("Flask"),
        requirement("setuptools"),
        requirement("waitress"),
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
        ":queue_consumer",
        "//truescrub/updater",
    ],
)

py_binary(
    name = "truescrub",
    srcs = ["__main__.py"],
    main = "__main__.py",
    visibility = ["//:__pkg__"],
    deps = [":application"],
)
