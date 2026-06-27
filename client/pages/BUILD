load("@aspect_rules_ts//ts:defs.bzl", "ts_project")

ts_project(
    name = "pages",
    srcs = ["AccoladesPage.tsx"],
    declaration = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//client/api",
        "//client/components",
        "//proto:highlights_service_js",
    ],
)
