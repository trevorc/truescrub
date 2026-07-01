load("@aspect_rules_ts//ts:defs.bzl", "ts_project")

ts_project(
    name = "accolade_card",
    srcs = [
        "AccoladeCard.tsx",
    ],
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
    declaration = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//proto:highlights_service_js",
        ":globals",
    ],
)

ts_project(
    name = "globals",
    srcs = ["globals.d.ts"],
    declaration = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
    visibility = ["//client:__subpackages__"],
)

ts_project(
    name = "navbar",
    srcs = ["Navbar.tsx"],
    declaration = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
    ],
)

ts_project(
    name = "footer",
    srcs = ["Footer.tsx"],
    declaration = True,
    transpiler = "tsc",
    tsconfig = "//:tsconfig",
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
    ],
)
