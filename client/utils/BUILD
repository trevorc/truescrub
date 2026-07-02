load("@aspect_rules_ts//ts:defs.bzl", "ts_project")

ts_project(
    name = "skill_group",
    srcs = ["skill_group.ts"],
    declaration = True,
    resolve_json_module = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//truescrub/proto:profile_js",
    ],
)
