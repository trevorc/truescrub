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
        "htdocs/img/c4.png",
        "htdocs/img/chicken_war.png",
        "htdocs/img/karambit.png",
    ],
    visibility = ["//client:__pkg__"],
)
