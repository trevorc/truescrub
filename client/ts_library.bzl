load("@aspect_rules_ts//ts:defs.bzl", _ts_project = "ts_project")

def ts_library(
        name,
        srcs = [],
        deps = [],
        tsconfig = "//:tsconfig",
        **kwargs):
    _ts_project(
        name = name,
        srcs = srcs,
        declaration = True,
        resolve_json_module = True,
        transpiler = "tsc",
        tsconfig = tsconfig,
        deps = deps,
        **kwargs
    )
