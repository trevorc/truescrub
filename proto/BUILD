load("@aspect_rules_js//js:defs.bzl", "js_library")
load("@aspect_rules_js//js:proto.bzl", "js_proto_toolchain")
load("@npm//:@bufbuild/protoc-gen-es/package_json.bzl", gen_es = "bin")
load("@protobuf//bazel:proto_library.bzl", "proto_library")
load("@rules_proto_grpc_python//:defs.bzl", "python_grpc_library")

package(default_visibility = ["//visibility:public"])

proto_library(
    name = "highlights_service_proto",
    srcs = ["highlights_service.proto"],
)

gen_es.protoc_gen_es_binary(name = "protoc_gen_es")

js_proto_toolchain(
    name = "gen_es_toolchain",
    out_dts_extension = "_pb.d.ts",
    out_js_extension = "_pb.js",
    plugin_bin = ":protoc_gen_es",
    plugin_name = "es",
    plugin_options = [
        "keep_empty_files=true",
        "target=js+dts",
    ],
    runtime = "//:node_modules/@bufbuild/protobuf",
)

js_library(
    name = "highlights_service_js",
    deps = [":highlights_service_proto"],
)

python_grpc_library(
    name = "highlights_service_py_pb2_grpc",
    protos = [":highlights_service_proto"],
)
