load("@aspect_rules_py//py:defs.bzl", "py_image_layer", "py_layer_tier")
load("@bazel_lib//lib:transitions.bzl", "platform_transition_filegroup")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@tar.bzl//:tar.bzl", "tar")

py_layer_tier(
    name = "tier",
    interpreter_group = "interpreter",
)

tar(
    name = "data_dir",
    mtree = ["data type=dir uid=65532 gid=65532 mode=0755"],
)

py_image_layer(
    name = "layer",
    binary = "//truescrub",
    layer_tier = ":tier",
)

platform_transition_filegroup(
    name = "layer_amd64",
    srcs = [":layer"],
    target_platform = "//platforms:linux_amd64",
)

platform_transition_filegroup(
    name = "layer_arm64",
    srcs = [":layer"],
    target_platform = "//platforms:linux_arm64",
)

ENTRYPOINT = [
    "/app.runfiles/_main/truescrub/._truescrub.venv/bin/python3",
    "/app.runfiles/_main/truescrub/__main__.py",
    "--addr=0.0.0.0",
    "--port=9000",
    "-s",
]

oci_image(
    name = "image_amd64",
    base = "@distroless_cc_linux_amd64",
    entrypoint = ENTRYPOINT,
    env = {
        "TRUESCRUB_DATA_DIR": "/data",
        "PYTHONPATH": "/app.runfiles/_main",
    },
    exposed_ports = ["9000/tcp"],
    tars = [
        ":data_dir",
        ":layer_amd64",
    ],
    user = "65532",
    workdir = "/app.runfiles/_main",
)

oci_image(
    name = "image_arm64",
    base = "@distroless_cc_linux_arm64_v8",
    entrypoint = ENTRYPOINT,
    env = {
        "TRUESCRUB_DATA_DIR": "/data",
        "PYTHONPATH": "/app.runfiles/_main",
    },
    exposed_ports = ["9000/tcp"],
    tars = [
        ":data_dir",
        ":layer_arm64",
    ],
    user = "65532",
    workdir = "/app.runfiles/_main",
)

oci_image_index(
    name = "image_index",
    images = [
        ":image_amd64",
        ":image_arm64",
    ],
)

oci_push(
    name = "push",
    image = ":image_index",
    remote_tags = ["latest"],
    repository = "localhost:5000/truescrub",
)

oci_load(
    name = "load_amd64",
    image = ":image_amd64",
    repo_tags = ["truescrub:latest"],
)
