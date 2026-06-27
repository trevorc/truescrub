load("@aspect_rules_esbuild//esbuild:defs.bzl", "esbuild")
load("@aspect_rules_ts//ts:defs.bzl", "ts_project")

ts_project(
    name = "entrypoints",
    srcs = ["accolades.ts"],
    declaration = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//client/api",
        "//client/pages",
        "//proto:highlights_service_js",
    ],
)

esbuild(
    name = "truescrub_api_bundle",
    entry_point = "accolades.js",
    minify = True,
    sourcemap = None,
    tsconfig = "//:tsconfig",
    visibility = ["//visibility:public"],
    deps = [":entrypoints"],
)
