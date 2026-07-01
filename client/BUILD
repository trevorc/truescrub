load("@aspect_rules_esbuild//esbuild:defs.bzl", "esbuild")
load("@aspect_rules_py//py:defs.bzl", "py_binary", "py_library", "py_test")
load("@aspect_rules_ts//ts:defs.bzl", "ts_config", "ts_project")
load("@bazel_skylib//rules:run_binary.bzl", "run_binary")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@rules_pkg//pkg:tar.bzl", "pkg_tar")
load("//client:rules/esbuild.bzl", "esbuild_metadata")

ts_project(
    name = "client_ts",
    srcs = ["TrueScrubClient.tsx"],
    declaration = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
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
        "//client/api",
        "//client/components:footer",
        "//client/components:navbar",
        "//client/pages:accolades_page",
        "//client/pages:home_page",
        "//client/pages:matchmaking_page",
        "//proto:highlights_service_js",
        "//proto:matchmaking_service_js",
    ],
)

esbuild(
    name = "client",
    config = "esbuild.config.mjs",
    entry_point = "TrueScrubClient.js",
    metafile = True,
    minify = True,
    output_dir = True,
    sourcemap = None,
    tsconfig = "//:tsconfig",
    visibility = ["//visibility:public"],
    deps = [":client_ts"],
)

esbuild_metadata(
    name = "client_metadata",
    target = ":client",
    visibility = ["//client/public:__pkg__"],
)

pkg_tar(
    name = "sws_config_layer",
    srcs = ["sws.toml"],
    package_dir = "/",
)

pkg_tar(
    name = "client_public_layer",
    srcs = [
        "//client/public:htdocs",
        "//client/public:index.html",
    ],
    package_dir = "/public",
    strip_prefix = "/client/public",
)

pkg_tar(
    name = "client_layer",
    srcs = [":client"],
    package_dir = "/public/htdocs",
    strip_prefix = "client",
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
