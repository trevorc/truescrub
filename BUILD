load("@aspect_rules_ts//ts:defs.bzl", "ts_config")
load("@bazel_lib//lib:copy_to_bin.bzl", "copy_to_bin")
load("@npm//:defs.bzl", "npm_link_all_packages")

npm_link_all_packages(name = "node_modules")

ts_config(
    name = "tsconfig",
    src = "tsconfig.json",
    visibility = ["//client:__subpackages__"],
)

ts_config(
    name = "tsconfig_test",
    src = "tsconfig.test.json",
    visibility = ["//client:__subpackages__"],
    deps = [":tsconfig"],
)

copy_to_bin(
    name = "jest_config",
    srcs = ["jest.config.js"],
    visibility = ["//client:__subpackages__"],
)
