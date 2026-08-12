load("@aspect_rules_esbuild//esbuild:defs.bzl", "esbuild")
load("@aspect_rules_jest//jest:defs.bzl", "jest_test")
load("@aspect_rules_js//js:defs.bzl", "js_binary", "js_library")
load("@bazel_lib//lib:directory_path.bzl", "directory_path")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@rules_pkg//pkg:tar.bzl", "pkg_tar")
load("//client:rules/esbuild.bzl", "esbuild_metadata")
load("//client:rules/tailwind.bzl", "tailwind_css")
load("//client:ts_library.bzl", "ts_library")

js_library(
    name = "test_setup",
    srcs = ["testSetup.js"],
    visibility = ["//client:__subpackages__"],
)


js_library(
    name = "file_mock",
    srcs = ["fileMock.js"],
    visibility = ["//client:__subpackages__"],
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
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
        "//client/api",
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

esbuild(
    name = "app_bundle",
    srcs = [
        "esbuild.config.mjs",
        ":style_bundle",
    ],
    config = "esbuild.config.mjs",
    entry_points = [
        "index.tsx",
        "style_bundle.css",
    ],
    metafile = True,
    minify = True,
    output_dir = True,
    sourcemap = None,
    tsconfig = "//:tsconfig",
    visibility = ["//visibility:public"],
    deps = [
        ":client_ts",
    ],
)

esbuild_metadata(
    name = "app_bundle_metadata",
    target = ":app_bundle",
    visibility = ["//client/public:__pkg__"],
)

directory_path(
    name = "tailwindcss_entrypoint",
    directory = "//:node_modules/@tailwindcss/cli/dir",
    path = "dist/index.mjs",
)

js_binary(
    name = "tailwindcss",
    data = [
        "//:node_modules/@tailwindcss/cli",
        "//:node_modules/tailwindcss",
    ],
    entry_point = ":tailwindcss_entrypoint",
    visibility = ["//client:__subpackages__"],
)

tailwind_css(
    name = "style_bundle",
    srcs = [":client_ts"],
    input = "style.css",
    visibility = ["//client:__subpackages__"],
)

pkg_tar(
    name = "sws_config_layer",
    srcs = ["sws.toml"],
    package_dir = "/",
)

pkg_tar(
    name = "client_public_layer",
    srcs = [
        "//client/public:favicon.png",
        "//client/public:index.html",
    ],
    package_dir = "/public",
    strip_prefix = "/client/public",
)

pkg_tar(
    name = "client_layer",
    srcs = [
        ":app_bundle",
    ],
    package_dir = "/public/htdocs",
    strip_prefix = "/client/app_bundle",
)

oci_image(
    name = "image_amd64",
    base = "@sws_base_linux_amd64",
    entrypoint = ["/static-web-server"],
    tars = [
        ":sws_config_layer",
        ":client_public_layer",
        ":client_layer",
    ],
)

oci_image(
    name = "image_arm64",
    base = "@sws_base_linux_arm64",
    entrypoint = ["/static-web-server"],
    tars = [
        ":sws_config_layer",
        ":client_public_layer",
        ":client_layer",
    ],
)

oci_image_index(
    name = "image",
    images = [
        ":image_amd64",
        ":image_arm64",
    ],
)

oci_push(
    name = "push",
    image = ":image",
    remote_tags = ["latest"],
    repository = "localhost:5000/truescrub-client",
)

ts_library(
    name = "client_ts_test_lib",
    srcs = ["TrueScrubClient.test.tsx"],
    tsconfig = "//:tsconfig_test",
    deps = [
        ":client_ts",
        "//:node_modules/@types/jest",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
    ],
)

jest_test(
    name = "client_ts_test",
    config = "//:jest_config",
    data = [
        ":client_ts_test_lib",
        "//:node_modules/ts-jest",
        "//:tsconfig",
        "//client:file_mock",
        "//client:test_setup",
        "//:node_modules/jest-environment-jsdom",
    ],
    node_modules = "//:node_modules",
)

