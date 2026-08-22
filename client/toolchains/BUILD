load("//client:rules/sws.bzl", "binary_toolchain")

package(default_visibility = ["//visibility:public"])

toolchain_type(name = "sws_toolchain_type")

binary_toolchain(
    name = "sws_linux_amd64",
    binary = "@sws_linux_amd64//:static-web-server",
)

binary_toolchain(
    name = "sws_linux_arm64",
    binary = "@sws_linux_arm64//:static-web-server",
)

toolchain(
    name = "sws_toolchain_linux_amd64",
    exec_compatible_with = [
        "@platforms//os:linux",
        "@platforms//cpu:x86_64",
    ],
    toolchain = ":sws_linux_amd64",
    toolchain_type = ":sws_toolchain_type",
)

toolchain(
    name = "sws_toolchain_linux_arm64",
    exec_compatible_with = [
        "@platforms//os:linux",
        "@platforms//cpu:aarch64",
    ],
    toolchain = ":sws_linux_arm64",
    toolchain_type = ":sws_toolchain_type",
)

toolchain_type(name = "tailwindcss_toolchain_type")

binary_toolchain(
    name = "tailwindcss_linux_amd64",
    binary = "@tailwindcss_linux_amd64//file:tailwindcss",
)

binary_toolchain(
    name = "tailwindcss_linux_arm64",
    binary = "@tailwindcss_linux_arm64//file:tailwindcss",
)

toolchain(
    name = "tailwindcss_toolchain_linux_amd64",
    exec_compatible_with = [
        "@platforms//os:linux",
        "@platforms//cpu:x86_64",
    ],
    toolchain = ":tailwindcss_linux_amd64",
    toolchain_type = ":tailwindcss_toolchain_type",
)

toolchain(
    name = "tailwindcss_toolchain_linux_arm64",
    exec_compatible_with = [
        "@platforms//os:linux",
        "@platforms//cpu:aarch64",
    ],
    toolchain = ":tailwindcss_linux_arm64",
    toolchain_type = ":tailwindcss_toolchain_type",
)
