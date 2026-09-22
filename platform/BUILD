package(default_visibility = ["//visibility:public"])

platform(
    name = "linux_amd64",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:x86_64",
    ],
    exec_properties = {
        "ISA": "x86_64",
        "OSFamily": "linux",
    },
)

platform(
    name = "linux_arm64",
    constraint_values = [
        "@platforms//os:linux",
        "@platforms//cpu:aarch64",
    ],
    exec_properties = {
        "ISA": "aarch64",
        "OSFamily": "linux",
    },
)

platform(
    name = "generic",
    constraint_values = [],
)

platform(
    name = "linux_generic",
    constraint_values = ["@platforms//os:linux"],
    exec_properties = {"OSFamily": "linux"},
)
