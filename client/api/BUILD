load("//client:rules/ts_library.bzl", "ts_library")

ts_library(
    name = "truescrub",
    srcs = ["truescrub.ts"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect",
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@connectrpc/connect-web",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
    ],
)

ts_library(
    name = "brand",
    srcs = ["brand.ts"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect",
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//proto:config_service_js",
    ],
)

ts_library(
    name = "seasons",
    srcs = ["seasons.ts"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect",
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//proto:season_service_js",
    ],
)
