load("@aspect_rules_esbuild//esbuild:defs.bzl", "esbuild")
load("@aspect_rules_ts//ts:defs.bzl", "ts_config")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@rules_pkg//pkg:tar.bzl", "pkg_tar")

esbuild(
    name = "client",
    entry_point = "//client/entrypoints",
    minify = True,
    sourcemap = None,
    tsconfig = "//:tsconfig",
    visibility = ["//visibility:public"],
    deps = ["//client/entrypoints"],
)

pkg_tar(
    name = "sws_config_layer",
    srcs = ["sws.toml"],
    package_dir = "/",
)

pkg_tar(
    name = "client_layer",
    srcs = [":client"],
    package_dir = "/public",
)

oci_image(
    name = "image_amd64",
    base = "@sws_base_linux_amd64",
    entrypoint = ["/static-web-server"],
    tars = [
        ":sws_config_layer",
        ":client_layer",
    ],
)

oci_image(
    name = "image_arm64",
    base = "@sws_base_linux_arm64",
    entrypoint = ["/static-web-server"],
    tars = [
        ":sws_config_layer",
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
