load("@pip_requirements//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_binary")

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
    name = "genetic",
    srcs = ["genetic.py"],
    deps = [
        "//truescrub:db",
        "//truescrub:models",
        "//truescrub/tools:teameval",
        requirement("deap"),
    ],
)

py_binary(
    name = "gstrans",
    srcs = ["gstrans.py"],
    deps = [
        "//truescrub:db",
        "//truescrub/statewriter",
        "//truescrub/statewriter:state_serialization",
        requirement("tqdm"),
    ],
)

py_binary(
    name = "logquery",
    srcs = ["logquery.py"],
    deps = [
        "//truescrub/statewriter",
        requirement("tqdm"),
    ],
)

py_binary(
    name = "dbsurgery",
    srcs = ["dbsurgery.py"],
    main = "dbsurgery.py",
    visibility = ["//:__pkg__"],
    deps = ["//truescrub:db"],
)

py_binary(
    name = "printaccolades",
    srcs = ["printaccolades.py"],
    deps = [
        "//truescrub:accolades",
        "//truescrub:highlights",
    ],
)
