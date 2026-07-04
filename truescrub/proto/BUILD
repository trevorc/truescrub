load("@aspect_rules_js//js:defs.bzl", "js_library")
load("@aspect_rules_ts//ts:proto.bzl", "ts_proto_library")
load("@protobuf//bazel:proto_library.bzl", "proto_library")
load("@protobuf//bazel:py_proto_library.bzl", "py_proto_library")

exports_files([
    "achievements.json",
    "skill_groups.json",
])

js_library(
    name = "achievements_json",
    srcs = ["achievements.json"],
    visibility = ["//client:__subpackages__"],
)

js_library(
    name = "skill_groups_json",
    srcs = ["skill_groups.json"],
    visibility = ["//client:__subpackages__"],
)

proto_library(
    name = "profile_proto",
    srcs = ["profile.proto"],
)

py_proto_library(
    name = "profile_py_pb2",
    visibility = [
        "//tests:__pkg__",
        "//truescrub:__subpackages__",
    ],
    deps = [":profile_proto"],
)

ts_proto_library(
    name = "profile_js",
    copy_files = False,
    node_modules = "//:node_modules",
    proto = ":profile_proto",
    protoc_gen_options = {
        "js_import_style": "legacy_commonjs",
    },
    visibility = ["//client:__subpackages__"],
)

proto_library(
    name = "game_state_proto",
    srcs = ["game_state.proto"],
    deps = ["@protobuf//:timestamp_proto"],
)

py_proto_library(
    name = "game_state_py_pb2",
    visibility = [
        "//tests:__pkg__",
        "//truescrub:__subpackages__",
    ],
    deps = [":game_state_proto"],
)
