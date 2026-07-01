load("@aspect_rules_py//py:defs.bzl", "py_binary", "py_library", "py_test")
load("@bazel_skylib//rules:run_binary.bzl", "run_binary")
load("@rules_pkg//pkg:tar.bzl", "pkg_tar")

py_library(
    name = "mkindex_lib",
    srcs = ["mkindex.py"],
)

py_binary(
    name = "mkindex",
    srcs = ["mkindex.py"],
    deps = [":mkindex_lib"],
)

py_test(
    name = "mkindex_test",
    srcs = ["mkindex_test.py"],
    deps = [":mkindex_lib"],
)

run_binary(
    name = "template_index",
    srcs = [
        "index.template.html",
        "//client:client_metadata",
    ],
    outs = ["index.html"],
    args = [
        "$(location //client:client_metadata)",
        "$(location index.template.html)",
        "$(location index.html)",
    ],
    tool = ":mkindex",
    visibility = ["//client:__pkg__"],
)

filegroup(
    name = "htdocs",
    srcs = [
        "htdocs/img/accolades_icon.png",
        "htdocs/img/achievements/distinct_maps.png",
        "htdocs/img/achievements/distinct_teammates.png",
        "htdocs/img/achievements/multi_kill_rounds.png",
        "htdocs/img/achievements/rounds_played.png",
        "htdocs/img/achievements/seasons_played.png",
        "htdocs/img/achievements/survived_losses.png",
        "htdocs/img/achievements/total_headshots.png",
        "htdocs/img/achievements/total_kills.png",
        "htdocs/img/achievements/total_mvps.png",
        "htdocs/img/achievements/zero_damage_rounds.png",
        "htdocs/img/c4.png",
        "htdocs/img/chicken_war.png",
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
    ],
    visibility = ["//client:__pkg__"],
)
