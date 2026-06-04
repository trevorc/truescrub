load("@rules_python//python:pip.bzl", "compile_pip_requirements")
load("@rules_python//python/zipapp:py_zipapp_binary.bzl", "py_zipapp_binary")

compile_pip_requirements(
    name = "requirements",
    extra_args = ["--allow-unsafe"],
    requirements_in = "requirements.in",
    requirements_txt = "requirements_lock.txt",
)

py_zipapp_binary(
    name = "truescrub_zip",
    binary = "//truescrub",
    visibility = ["//:__pkg__"],
)

py_zipapp_binary(
    name = "surgery_zip",
    binary = "//truescrub/tools:surgery",
)
