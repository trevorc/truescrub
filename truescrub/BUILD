load("@pip_requirements//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_binary", "py_library")

package(
    default_visibility = [
        "//tests:__pkg__",
        "//truescrub/statewriter:__pkg__",
        "//truescrub/tools:__pkg__",
        "//truescrub/updater:__pkg__",
    ],
)

py_library(
    name = "envconfig",
    srcs = ["envconfig.py"],
    visibility = ["//truescrub:__subpackages__"],
)

py_library(
    name = "seasoncfg",
    srcs = ["seasoncfg.py"],
    deps = [":envconfig"],
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
        ":envconfig",
        ":models",
        requirement("trueskill"),
    ],
)

py_library(
    name = "queue_consumer",
    srcs = ["queue_consumer.py"],
)

py_library(
    name = "highlights",
    srcs = ["highlights.py"],
    deps = [
        ":accolades",
        ":db",
        ":models",
    ],
)

py_binary(
    name = "accolades",
    srcs = ["accolades.py"],
    data = ["accolades.ini"],
    visibility = [
        "//tests:__pkg__",
        "//truescrub/tools:__pkg__",
    ],
    deps = [
        ":db",
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
        ":accolades",
        ":db",
        ":highlights",
        ":matchmaking",
        ":models",
        requirement("Flask"),
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
        "//truescrub/proto:game_state_py_pb2",
        "//truescrub/statewriter",
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
