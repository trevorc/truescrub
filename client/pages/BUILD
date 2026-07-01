load("@aspect_rules_ts//ts:defs.bzl", "ts_project")

ts_project(
    name = "home_page",
    srcs = ["HomePage.tsx"],
    declaration = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
        "//client/api",
        "//client/components:globals",
        "//proto:matchmaking_service_js",
        "//proto:season_service_js",
    ],
)

ts_project(
    name = "matchmaking_page",
    srcs = ["MatchmakingPage.tsx"],
    declaration = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
        "//client/api",
        "//proto:matchmaking_service_js",
        "//proto:season_service_js",
    ],
)

ts_project(
    name = "accolades_page",
    srcs = ["AccoladesPage.tsx"],
    assets = [
        "chickens/chicken_ui.png",
        "chickens/chicken_ui2.png",
        "chickens/chicken_ui3.png",
        "chickens/chicken_ui4.png",
        "chickens/chicken_ui5.png",
    ],
    declaration = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
        "//client/components:accolade_card",
        "//client/components:globals",
        "//proto:highlights_service_js",
    ],
)
