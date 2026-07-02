load("@aspect_rules_esbuild//esbuild:defs.bzl", "esbuild")
load("@aspect_rules_js//js:defs.bzl", "js_binary")
load("@aspect_rules_py//py:defs.bzl", "py_binary", "py_library", "py_test")
load("@bazel_lib//lib:directory_path.bzl", "directory_path")
load("@bazel_skylib//rules:run_binary.bzl", "run_binary")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@rules_pkg//pkg:tar.bzl", "pkg_tar")
load("//client:rules/esbuild.bzl", "esbuild_metadata")
load("//client:rules/tailwind.bzl", "tailwind_css")
load("//client:ts_library.bzl", "ts_library")

exports_files([
    "esbuild.config.mjs",
])

ts_library(
    name = "client_ts",
    srcs = ["TrueScrubClient.tsx"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/@types/react-router-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
        "//:node_modules/recharts",
        "//:node_modules/redux",
        "//client/api",
        "//client/components:footer",
        "//client/components:navbar",
        "//client/pages:accolades_page",
        "//client/pages:home_page",
        "//client/pages:leaderboard_page",
        "//client/pages:matchmaking_page",
        "//client/pages:not_found_page",
        "//client/pages:profile_page",
        "//client/pages:skill_groups_page",
        "//proto:highlights_service_js",
        "//proto:matchmaking_service_js",
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
        "TrueScrubClient.js",
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
        ":client_layer",
        ":client_public_layer",
    ],
)

oci_image(
    name = "image_arm64",
    base = "@sws_base_linux_arm64",
    entrypoint = ["/static-web-server"],
    tars = [
        ":sws_config_layer",
        ":client_layer",
        ":client_public_layer",
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
