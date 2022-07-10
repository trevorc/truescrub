load("@rules_python//python:defs.bzl", "py_binary")
load("@pip_requirements//:requirements.bzl", "requirement")
load("@subpar//:subpar.bzl", "par_binary")

py_binary(
    name = "teameval",
    srcs = [
        "teameval.py",
    ],
    deps = [
        "//truescrub:db",
        "//truescrub:matchmaking",
        "//truescrub:models",
    ],
)

py_binary(
    name = "gstrans",
    srcs = ["gstrans.py"],
    deps = [
        "//truescrub:db",
        "//truescrub:state_serialization",
        requirement("tqdm"),
    ],
)

par_binary(
    name = "dbsurgery",
    srcs = ["dbsurgery.py"],
    main = "dbsurgery.py",
    deps = [
        "//truescrub:db",
    ],
)
