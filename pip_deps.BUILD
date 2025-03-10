package(default_visibility = ["//visibility:public"])

# Make all Python modules available
filegroup(
    name = "site-packages",
    srcs = glob(["**/*.py"], exclude=["**/__pycache__/**"]),
)

# Define targets for each pip package
py_library(
    name = "attrs",
    srcs = glob(["attrs/**/*.py", "attr/**/*.py"]),
    imports = ["."],
    visibility = ["//visibility:public"],
)

py_library(
    name = "Flask",
    srcs = glob(["flask/**/*.py"]),
    imports = ["."],
    visibility = ["//visibility:public"],
)

py_library(
    name = "setuptools",
    srcs = glob(["setuptools/**/*.py"]),
    imports = ["."],
    visibility = ["//visibility:public"],
)

py_library(
    name = "waitress",
    srcs = glob(["waitress/**/*.py"]),
    imports = ["."],
    visibility = ["//visibility:public"],
)

py_library(
    name = "six",
    srcs = ["six.py"],
    imports = ["."],
    visibility = ["//visibility:public"],
)

py_library(
    name = "trueskill",
    srcs = glob(["trueskill/**/*.py"]),
    imports = ["."],
    deps = [":six"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "py",
    srcs = glob(["py/**/*.py"]),
    imports = ["."],
    visibility = ["//visibility:public"],
)

py_library(
    name = "pluggy",
    srcs = glob(["pluggy/**/*.py"]),
    imports = ["."],
    visibility = ["//visibility:public"],
)

py_library(
    name = "iniconfig",
    srcs = glob(["iniconfig/**/*.py"]),
    imports = ["."],
    visibility = ["//visibility:public"],
)

py_library(
    name = "pytest",
    srcs = glob(["pytest/**/*.py", "_pytest/**/*.py"]),
    imports = ["."],
    deps = [
        ":py",
        ":pluggy",
        ":iniconfig",
        ":attrs",
    ],
    visibility = ["//visibility:public"],
)

py_library(
    name = "deap",
    srcs = glob(["deap/**/*.py"]),
    imports = ["."],
    visibility = ["//visibility:public"],
)

py_library(
    name = "tqdm",
    srcs = glob(["tqdm/**/*.py"]),
    imports = ["."],
    visibility = ["//visibility:public"],
)