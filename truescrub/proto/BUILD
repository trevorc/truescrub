load("@rules_proto//proto:defs.bzl", "proto_library")
load("@rules_python//python:defs.bzl", "py_library")

proto_library(
    name = "game_state_proto",
    srcs = ["game_state.proto"],
    deps = ["@com_google_protobuf//:timestamp_proto"],
)

# Simple py_library that wraps the proto outputs
py_library(
    name = "game_state_py_proto",
    srcs = ["game_state_pb2.py"],
    data = [":game_state_proto"],
    imports = ["."],
    visibility = ["//truescrub:__pkg__"],
)

# Add the generated type stub file
filegroup(
    name = "proto_type_stubs",
    srcs = ["game_state_pb2.pyi"],
    visibility = ["//visibility:public"],
)
