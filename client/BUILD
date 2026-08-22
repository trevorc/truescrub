load("@aspect_rules_esbuild//esbuild:defs.bzl", "esbuild")
load("@aspect_rules_jest//jest:defs.bzl", "jest_test")
load("@bazel_lib//lib:copy_to_directory.bzl", "copy_to_directory")
load("@bazel_lib//lib:transitions.bzl", "platform_transition_filegroup")
load("@bazel_skylib//rules:write_file.bzl", "write_file")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@tar.bzl", "mutate", "tar")
load("//client:rules/sws.bzl", "sws")
load("//client:rules/tailwind.bzl", "tailwind_css")
load("//client:rules/ts_library.bzl", "ts_library")

config_setting(
    name = "minify",
    values = {"compilation_mode": "opt"},
)

ts_library(
    name = "test_setup",
    testonly = True,
    srcs = ["testSetup.ts"],
    tsconfig = "//:tsconfig_test",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@types/jest",
        "//:node_modules/@types/node",
        "//:node_modules/whatwg-fetch",
    ],
)

ts_library(
    name = "file_mock",
    testonly = True,
    srcs = ["fileMock.ts"],
    tsconfig = "//:tsconfig_test",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@types/jest",
        "//:node_modules/@types/node",
    ],
)

ts_library(
    name = "client_ts",
    srcs = [
        "TrueScrubClient.tsx",
        "index.tsx",
    ],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-router-dom",
        "//client/api:brand",
        "//client/api:seasons",
        "//client/api:truescrub",
        "//client/layouts:root_layout",
        "//client/pages:accolades_page",
        "//client/pages:home_page",
        "//client/pages:leaderboard_page",
        "//client/pages:matchmaking_page",
        "//client/pages:not_found_page",
        "//client/pages:profile_page",
        "//client/pages:skill_groups_page",
    ],
)

BASE_ESBUILD_CONFIG = {
    "assetNames": "assets/[name]-[hash]",
    "entryNames": "[name]-[hash]",
    "format": "esm",
    "loader": {".png": "file"},
    "publicPath": "/htdocs/",
}

write_file(
    name = "esbuild_dev_config",
    out = "esbuild.dev.config.mjs",
    content = ["export default " + json.encode(BASE_ESBUILD_CONFIG)],
)

write_file(
    name = "esbuild_prod_config",
    out = "esbuild.prod.config.mjs",
    content = ["export default " + json.encode(dict(
        BASE_ESBUILD_CONFIG,
        conditions = [
            "production",
            "browser",
            "import",
        ],
    ))],
)

esbuild(
    name = "app_bundle",
    srcs = [":style_bundle"],
    config = select({
        ":minify": ":esbuild.prod.config.mjs",
        "//conditions:default": ":esbuild.dev.config.mjs",
    }),
    entry_points = [
        "index.tsx",
        ":style_bundle",
    ],
    metafile = True,
    minify = select({
        ":minify": True,
        "//conditions:default": False,
    }),
    output_dir = True,
    sourcemap = None,
    tsconfig = "//:tsconfig",
    visibility = ["//visibility:public"],
    deps = [":client_ts"],
)

filegroup(
    name = "app_bundle_metadata",
    srcs = [":app_bundle"],
    output_group = "metafile",
    visibility = ["//client/public:__pkg__"],
)

tailwind_css(
    name = "style_bundle",
    srcs = [":client_ts"],
    input = "style.css",
    visibility = ["//client:__subpackages__"],
)

copy_to_directory(
    name = "client_assets",
    srcs = [
        ":app_bundle",
        "//client/public:favicon.png",
        "//client/public:index.html",
    ],
    replace_prefixes = {
        "public/": "",
        "app_bundle/": "htdocs/",
    },
)

sws(
    name = "server",
    assets = ":client_assets",
    config = "sws.toml",
)

tar(
    name = "sws_config_layer_tar",
    srcs = ["sws.toml"],
    mutate = mutate(package_dir = "/"),
)

platform_transition_filegroup(
    name = "sws_config_layer",
    srcs = [":sws_config_layer_tar"],
    target_platform = "//platform:linux_amd64",
)

tar(
    name = "sws_bin_linux_amd64",
    srcs = ["@sws_linux_amd64//:static-web-server"],
    mutate = mutate(package_dir = "/"),
)

tar(
    name = "sws_bin_linux_arm64",
    srcs = ["@sws_linux_arm64//:static-web-server"],
    mutate = mutate(package_dir = "/"),
)

tar(
    name = "client_layer_tar",
    srcs = [":client_assets"],
    mutate = mutate(
        package_dir = "/public",
        strip_prefix = "client/client_assets",
    ),
)

platform_transition_filegroup(
    name = "client_layer",
    srcs = [":client_layer_tar"],
    target_platform = "//platform:linux_amd64",
)

oci_image(
    name = "image",
    architecture = select({
        "@platforms//cpu:aarch64": "arm64",
        "@platforms//cpu:x86_64": "amd64",
    }),
    entrypoint = ["/static-web-server"],
    env = {
        "SERVER_CONFIG_FILE": "/sws.toml",
        "SERVER_ROOT": "/public",
    },
    os = "linux",
    tars = [":sws_config_layer"] + select({
        "@platforms//cpu:aarch64": [":sws_bin_linux_arm64"],
        "@platforms//cpu:x86_64": [":sws_bin_linux_amd64"],
    }) + [":client_layer"],
    user = "65532:65532",
)

oci_image_index(
    name = "image_index",
    images = [":image"],
    platforms = [
        "//platform:linux_amd64",
        "//platform:linux_arm64",
    ],
)

oci_push(
    name = "push",
    image = ":image_index",
)

ts_library(
    name = "client_ts_test_lib",
    testonly = True,
    srcs = ["TrueScrubClient.test.tsx"],
    tsconfig = "//:tsconfig_test",
    deps = [
        ":client_ts",
        "//:node_modules/@connectrpc/connect",
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@testing-library/react",
        "//:node_modules/@types/jest",
        "//:node_modules/@types/node",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-router-dom",
        "//client/api:brand",
        "//client/api:truescrub",
        "//proto:config_service_js",
        "//proto:season_service_js",
    ],
)

jest_test(
    name = "client_ts_test",
    config = "//:jest.config.js",
    data = [
        ":client_ts_test_lib",
        "//:jest_config",
        "//:node_modules/jest-environment-jsdom",
        "//client:file_mock",
        "//client:test_setup",
    ],
    node_modules = "//:node_modules",
)
