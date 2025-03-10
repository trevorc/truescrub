load("@rules_python//python:pip.bzl", "compile_pip_requirements")

compile_pip_requirements(
    name = "requirements",
    extra_args = ["--allow-unsafe"],
    requirements_in = "requirements.in",
    requirements_txt = "requirements_lock.txt",
)

# Custom requirement function to integrate with virtualenv
cc_library(
    name = "requirement_lib",
    hdrs = ["requirements.bzl"],
    visibility = ["//visibility:public"],
)

exports_files(["requirements.bzl"])

filegroup(
    name = "truescrub_zip",
    srcs = ["//truescrub"],
    output_group = "python_zip_file",
    visibility = ["//:__pkg__"],
)

filegroup(
    name = "dbsurgery_zip",
    srcs = ["//truescrub/tools:dbsurgery"],
    output_group = "python_zip_file",
)
