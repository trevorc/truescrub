load("@aspect_rules_jest//jest:defs.bzl", "jest_test")
load("//client:ts_library.bzl", "ts_library")

ts_library(
    name = "root_layout",
    srcs = ["RootLayout.tsx"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/react",
        "//:node_modules/react-router-dom",
        "//client/components:footer",
        "//client/components:navbar",
    ],
)

ts_library(
    name = "root_layout_test_lib",
    srcs = ["RootLayout.test.tsx"],
    tsconfig = "//:tsconfig_test",
    deps = [
        ":root_layout",
        "//:node_modules/@types/jest",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
    ],
)

jest_test(
    name = "root_layout_test",
    config = "//:jest_config",
    data = [
        ":root_layout_test_lib",
        "//:node_modules/ts-jest",
        "//:tsconfig",
        "//client:file_mock",
        "//client:test_setup",
        "//:node_modules/jest-environment-jsdom",
    ],
    node_modules = "//:node_modules",
)
