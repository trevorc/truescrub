load("@aspect_rules_ts//ts:proto.bzl", "ts_proto_library")
load("@grpc//bazel:python_rules.bzl", "py_grpc_library")
load("@protobuf//bazel:proto_library.bzl", "proto_library")
load("@protobuf//bazel:py_proto_library.bzl", "py_proto_library")

package(default_visibility = ["//visibility:public"])

proto_library(
    name = "common_proto",
    srcs = ["common.proto"],
)

py_proto_library(
    name = "common_py_pb2",
    deps = [":common_proto"],
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

py_proto_library(
    name = "highlights_service_py_pb2",
    deps = [":highlights_service_proto"],
)

py_grpc_library(
    name = "highlights_service_py_pb2_grpc",
    srcs = [":highlights_service_proto"],
    grpc_library = "//toolchains:pypi_grpcio",
    deps = [":highlights_service_py_pb2"],
)

proto_library(
    name = "matchmaking_service_proto",
    srcs = ["matchmaking_service.proto"],
    deps = [":common_proto"],
)

py_proto_library(
    name = "matchmaking_service_py_pb2",
    deps = [":matchmaking_service_proto"],
)

py_grpc_library(
    name = "matchmaking_service_py_pb2_grpc",
    srcs = [":matchmaking_service_proto"],
    grpc_library = "//toolchains:pypi_grpcio",
    deps = [":matchmaking_service_py_pb2"],
)

proto_library(
    name = "season_service_proto",
    srcs = ["season_service.proto"],
)

py_proto_library(
    name = "season_service_py_pb2",
    deps = [":season_service_proto"],
)

py_grpc_library(
    name = "season_service_py_pb2_grpc",
    srcs = [":season_service_proto"],
    grpc_library = "//toolchains:pypi_grpcio",
    deps = [":season_service_py_pb2"],
)

proto_library(
    name = "leaderboard_service_proto",
    srcs = ["leaderboard_service.proto"],
    deps = [":common_proto"],
)

py_proto_library(
    name = "leaderboard_service_py_pb2",
    deps = [":leaderboard_service_proto"],
)

py_grpc_library(
    name = "leaderboard_service_py_pb2_grpc",
    srcs = [":leaderboard_service_proto"],
    grpc_library = "//toolchains:pypi_grpcio",
    deps = [":leaderboard_service_py_pb2"],
)

ts_proto_library(
    name = "common_js",
    copy_files = False,
    node_modules = "//:node_modules",
    proto = ":common_proto",
    protoc_gen_options = {
        "js_import_style": "legacy_commonjs",
    },
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
    protoc_gen_options = {
        "js_import_style": "legacy_commonjs",
    },
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
    protoc_gen_options = {
        "js_import_style": "legacy_commonjs",
    },
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
    protoc_gen_options = {
        "js_import_style": "legacy_commonjs",
    },
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
    protoc_gen_options = {
        "js_import_style": "legacy_commonjs",
    },
    deps = [":common_js"],
)

proto_library(
    name = "profile_service_proto",
    srcs = ["profile_service.proto"],
    deps = [":common_proto"],
)

py_proto_library(
    name = "profile_service_py_pb2",
    deps = [":profile_service_proto"],
)

py_grpc_library(
    name = "profile_service_py_pb2_grpc",
    srcs = [":profile_service_proto"],
    grpc_library = "//toolchains:pypi_grpcio",
    deps = [":profile_service_py_pb2"],
)

ts_proto_library(
    name = "profile_service_js",
    copy_files = False,
    gen_connect_query = True,
    gen_connect_query_service_mapping = {
        "profile_service.proto": ["ProfileService"],
    },
    node_modules = "//:node_modules",
    proto = ":profile_service_proto",
    protoc_gen_options = {
        "js_import_style": "legacy_commonjs",
    },
    deps = [":common_js"],
)

proto_library(
    name = "config_service_proto",
    srcs = ["config_service.proto"],
)

py_proto_library(
    name = "config_service_py_pb2",
    deps = [":config_service_proto"],
)

py_grpc_library(
    name = "config_service_py_pb2_grpc",
    srcs = [":config_service_proto"],
    grpc_library = "//toolchains:pypi_grpcio",
    deps = [":config_service_py_pb2"],
)

ts_proto_library(
    name = "config_service_js",
    copy_files = False,
    gen_connect_query = True,
    gen_connect_query_service_mapping = {
        "config_service.proto": ["ConfigService"],
    },
    node_modules = "//:node_modules",
    proto = ":config_service_proto",
    protoc_gen_options = {
        "js_import_style": "legacy_commonjs",
    },
)
