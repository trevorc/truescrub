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
        "htdocs/img/accolades/bench_warmer.png",
        "htdocs/img/accolades/big_oofs.png",
        "htdocs/img/accolades/blind_fire.png",
        "htdocs/img/accolades/brick.png",
        "htdocs/img/accolades/cannon_fodder.png",
        "htdocs/img/accolades/grand_slamma_jamma.png",
        "htdocs/img/accolades/hard_carry.png",
        "htdocs/img/accolades/high_roller.png",
        "htdocs/img/accolades/just_uninstall.png",
        "htdocs/img/accolades/moral_support.png",
        "htdocs/img/accolades/pacifist.png",
        "htdocs/img/accolades/participation_award.png",
        "htdocs/img/accolades/stealthy_strategist.png",
        "htdocs/img/accolades/team_player.png",
        "htdocs/img/accolades/top_frag.png",
        "htdocs/img/accolades/un_mvp.png",
        "htdocs/img/accolades/untouchable.png",
        "htdocs/img/accolades/winner_winner_chicken_dinner.png",
        "htdocs/img/accolades_icon.png",
        "htdocs/img/c4.png",
        "htdocs/img/chicken.png",
        "htdocs/img/karambit.png",
        "htdocs/img/ranks/cardboard_i.png",
        "htdocs/img/ranks/cardboard_ii.png",
        "htdocs/img/ranks/cardboard_iii.png",
        "htdocs/img/ranks/cardboard_iv.png",
        "htdocs/img/ranks/garb_salad.png",
        "htdocs/img/ranks/legendary_wood.png",
        "htdocs/img/ranks/low_key_dirty.png",
        "htdocs/img/ranks/master_garbian.png",
        "htdocs/img/ranks/master_garbian_elite.png",
        "htdocs/img/ranks/plastic_elite.png",
        "htdocs/img/ranks/plastic_i.png",
        "htdocs/img/ranks/plastic_ii.png",
        "htdocs/img/ranks/plastic_iii.png",
        "htdocs/vendor/highcharts-8.0.0.js",
        "htdocs/vendor/highcharts-more-8.0.0.js",
        "templates/accolades.html",
        "templates/index.html",
        "templates/layout.html",
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
