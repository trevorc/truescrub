load("@aspect_rules_ts//ts:proto.bzl", "ts_proto_library")
load("@protobuf//bazel:proto_library.bzl", "proto_library")
load("@rules_proto_grpc_python//:defs.bzl", "python_grpc_library", "python_proto_library")

package(default_visibility = ["//visibility:public"])

proto_library(
    name = "common_proto",
    srcs = ["common.proto"],
)

python_proto_library(
    name = "common_py_pb2",
    protos = [":common_proto"],
)

proto_library(
    name = "highlights_service_proto",
    srcs = ["highlights_service.proto"],
    deps = [
        ":common_proto",
        "@protobuf//:field_mask_proto",
        "@protobuf//:timestamp_proto",
    ],
)

python_grpc_library(
    name = "highlights_service_py_pb2_grpc",
    protos = [":highlights_service_proto"],
)

proto_library(
    name = "matchmaking_service_proto",
    srcs = ["matchmaking_service.proto"],
    deps = [":common_proto"],
)

python_grpc_library(
    name = "matchmaking_service_py_pb2_grpc",
    protos = [":matchmaking_service_proto"],
)

proto_library(
    name = "season_service_proto",
    srcs = ["season_service.proto"],
)

python_grpc_library(
    name = "season_service_py_pb2_grpc",
    protos = [":season_service_proto"],
)

proto_library(
    name = "leaderboard_service_proto",
    srcs = ["leaderboard_service.proto"],
    deps = [":common_proto"],
)

python_grpc_library(
    name = "leaderboard_service_py_pb2_grpc",
    protos = [":leaderboard_service_proto"],
)

ts_proto_library(
    name = "common_js",
    copy_files = False,
    node_modules = "//:node_modules",
    proto = ":common_proto",
)

ts_proto_library(
    name = "highlights_service_js",
    copy_files = False,
    gen_connect_query = True,
    gen_connect_query_service_mapping = {
        "highlights_service.proto": ["HighlightsService"],
    },
    node_modules = "//:node_modules",
    proto = ":highlights_service_proto",
    deps = [":common_js"],
)

ts_proto_library(
    name = "matchmaking_service_js",
    copy_files = False,
    gen_connect_query = True,
    gen_connect_query_service_mapping = {
        "matchmaking_service.proto": ["MatchmakingService"],
    },
    node_modules = "//:node_modules",
    proto = ":matchmaking_service_proto",
    deps = [":common_js"],
)

ts_proto_library(
    name = "season_service_js",
    copy_files = False,
    gen_connect_query = True,
    gen_connect_query_service_mapping = {
        "season_service.proto": ["SeasonService"],
    },
    node_modules = "//:node_modules",
    proto = ":season_service_proto",
)

ts_proto_library(
    name = "leaderboard_service_js",
    copy_files = False,
    gen_connect_query = True,
    gen_connect_query_service_mapping = {
        "leaderboard_service.proto": ["LeaderboardService"],
    },
    node_modules = "//:node_modules",
    proto = ":leaderboard_service_proto",
    deps = [":common_js"],
)
