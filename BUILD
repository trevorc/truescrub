load("@aspect_rules_ts//ts:defs.bzl", "ts_config")
load("@npm//:defs.bzl", "npm_link_all_packages")
load("//client:rules/ts_library.bzl", "ts_library")

npm_link_all_packages(name = "node_modules")

ts_config(
    name = "tsconfig",
    src = "tsconfig.json",
    visibility = [
        "//client:__subpackages__",
        "//truescrub:__subpackages__",
    ],
)

ts_config(
    name = "tsconfig_test",
    testonly = True,
    src = "tsconfig.test.json",
    visibility = [
        "//client:__subpackages__",
        "//truescrub:__subpackages__",
    ],
    deps = [":tsconfig"],
)

ts_library(
    name = "jest_config",
    testonly = True,
    srcs = ["jest.config.ts"],
    tsconfig = "//:tsconfig_test",
    visibility = [
        "//client:__subpackages__",
        "//truescrub:__subpackages__",
    ],
    deps = [
        "//:node_modules/@jest/types",
        "//:node_modules/@types/jest",
        "//:node_modules/@types/node",
    ],
)
