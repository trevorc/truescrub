load("//client:ts_library.bzl", "ts_library")

ts_library(
    name = "api",
    srcs = ["truescrub.ts"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect",
        "//:node_modules/@connectrpc/connect-web",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
    ],
)
