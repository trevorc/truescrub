load("@aspect_rules_ts//ts:defs.bzl", "ts_project")

ts_project(
    name = "api",
    srcs = ["truescrub.ts"],
    declaration = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect",
        "//:node_modules/@connectrpc/connect-web",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
    ],
)
