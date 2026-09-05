load("@aspect_rules_jest//jest:defs.bzl", "jest_test")
load("//client:rules/ts_library.bzl", "ts_library")

ts_library(
    name = "root_layout",
    srcs = ["RootLayout.tsx"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@tanstack/react-router",
        "//:node_modules/react",
        "//client/api:brand",
        "//client/api:truescrub",
        "//client/components:footer",
        "//client/components:loading_state",
        "//client/components:navbar",
    ],
)

ts_library(
    name = "root_layout_test_lib",
    testonly = True,
    srcs = ["RootLayout.test.tsx"],
    tsconfig = "//:tsconfig_test",
    deps = [
        ":root_layout",
        "//:node_modules/@connectrpc/connect",
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@tanstack/react-router",
        "//:node_modules/@testing-library/react",
        "//:node_modules/@types/jest",
        "//:node_modules/@types/node",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//client/api:brand",
        "//proto:config_service_js",
    ],
)

jest_test(
    name = "root_layout_test",
    config = "//:jest.config.js",
    data = [
        ":root_layout_test_lib",
        "//:jest_config",
        "//:node_modules/jest-environment-jsdom",
        "//client:file_mock",
        "//client:test_setup",
    ],
    node_modules = "//:node_modules",
)
