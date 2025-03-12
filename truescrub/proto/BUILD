load("@rules_proto//proto:defs.bzl", "proto_library")
load("@com_google_protobuf//bazel:py_proto_library.bzl", "py_proto_library")

proto_library(
    name = "game_state_proto",
    srcs = ["game_state.proto"],
    deps = ["@com_google_protobuf//:timestamp_proto"],
)

py_proto_library(
    name = "game_state_py_pb2",
    visibility = ["//truescrub:__pkg__"],
    deps = [":game_state_proto"],
)
