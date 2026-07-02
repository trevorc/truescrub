load("//client:ts_library.bzl", "ts_library")

ts_library(
    name = "accolade_card",
    srcs = ["AccoladeCard.tsx"],
    assets = [
        "accolades/bench_warmer.png",
        "accolades/big_oofs.png",
        "accolades/blind_fire.png",
        "accolades/brick.png",
        "accolades/cannon_fodder.png",
        "accolades/decoy.png",
        "accolades/efficiency_expert.png",
        "accolades/glass_cannon.png",
        "accolades/grand_slamma_jamma.png",
        "accolades/hard_carry.png",
        "accolades/headshot_hunter.png",
        "accolades/high_roller.png",
        "accolades/just_uninstall.png",
        "accolades/moral_support.png",
        "accolades/pacifist.png",
        "accolades/participation_award.png",
        "accolades/stealthy_strategist.png",
        "accolades/team_player.png",
        "accolades/top_frag.png",
        "accolades/un_mvp.png",
        "accolades/untouchable.png",
        "accolades/wallflower.png",
        "accolades/winner_winner_chicken_dinner.png",
        "img/chicken.png",
    ],
    visibility = ["//client:__subpackages__"],
    deps = [
        ":globals",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//proto:highlights_service_js",
    ],
)

ts_library(
    name = "globals",
    srcs = ["globals.d.ts"],
    visibility = ["//client:__subpackages__"],
)

ts_library(
    name = "navbar",
    srcs = ["Navbar.tsx"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
    ],
)

ts_library(
    name = "footer",
    srcs = ["Footer.tsx"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
    ],
)

ts_library(
    name = "error_state",
    srcs = ["ErrorState.tsx"],
    assets = [
        "img/chicken_error.png",
        "img/chicken_error2.png",
        "img/chicken_error3.png",
    ],
    visibility = ["//client:__subpackages__"],
    deps = [
        ":globals",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
    ],
)

ts_library(
    name = "loading_state",
    srcs = ["LoadingState.tsx"],
    assets = [
        "chickens/chicken_ui.png",
        "chickens/chicken_ui2.png",
        "chickens/chicken_ui3.png",
        "chickens/chicken_ui4.png",
        "chickens/chicken_ui5.png",
        "chickens/chicken_ui6.png",
        "chickens/chicken_ui7.png",
    ],
    visibility = ["//client:__subpackages__"],
    deps = [
        ":globals",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
    ],
)
