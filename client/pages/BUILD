load("@aspect_rules_jest//jest:defs.bzl", "jest_test")
load("//client:rules/ts_library.bzl", "ts_library")

ts_library(
    name = "home_page",
    srcs = ["HomePage.tsx"],
    assets = [
        "img/accolades_icon.png",
        "img/c4.png",
        "img/karambit.png",
    ],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
        "//client/api:brand",
        "//client/api:seasons",
        "//client/api:truescrub",
        "//client/components:globals",
        "//proto:season_service_js",
    ],
)

ts_library(
    name = "matchmaking_page",
    srcs = ["MatchmakingPage.tsx"],
    assets = ["img/chicken_war.png"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
        "//client/api:seasons",
        "//client/api:truescrub",
        "//client/components:error_state",
        "//client/components:loading_state",
        "//proto:matchmaking_service_js",
        "//proto:season_service_js",
    ],
)

ts_library(
    name = "accolades_page",
    srcs = ["AccoladesPage.tsx"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
        "//client/api:truescrub",
        "//client/components:accolade_card",
        "//client/components:error_state",
        "//client/components:globals",
        "//client/components:loading_state",
        "//proto:highlights_service_js",
    ],
)

ts_library(
    name = "skill_groups_page",
    srcs = ["SkillGroupsPage.tsx"],
    assets = [
        "ranks/cardboard_i.png",
        "ranks/cardboard_ii.png",
        "ranks/cardboard_iii.png",
        "ranks/cardboard_iv.png",
        "ranks/garb_salad.png",
        "ranks/legendary_wood.png",
        "ranks/low_key_dirty.png",
        "ranks/master_garbian.png",
        "ranks/master_garbian_elite.png",
        "ranks/plastic_elite.png",
        "ranks/plastic_i.png",
        "ranks/plastic_ii.png",
        "ranks/plastic_iii.png",
    ],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@bufbuild/protobuf",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//client/components:globals",
        "//truescrub/proto:profile_js",
        "//truescrub/proto:skill_groups_json",
    ],
)

ts_library(
    name = "leaderboard_page",
    srcs = ["LeaderboardPage.tsx"],
    assets = [
        "ranks/cardboard_i.png",
        "ranks/cardboard_ii.png",
        "ranks/cardboard_iii.png",
        "ranks/cardboard_iv.png",
        "ranks/garb_salad.png",
        "ranks/legendary_wood.png",
        "ranks/low_key_dirty.png",
        "ranks/master_garbian.png",
        "ranks/master_garbian_elite.png",
        "ranks/plastic_elite.png",
        "ranks/plastic_i.png",
        "ranks/plastic_ii.png",
        "ranks/plastic_iii.png",
    ],
    visibility = ["//client:__subpackages__"],
    deps = [
        ":skill_group",
        "//:node_modules/@bufbuild/protobuf",
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
        "//client/api:brand",
        "//client/api:seasons",
        "//client/api:truescrub",
        "//client/components:error_state",
        "//client/components:globals",
        "//client/components:loading_state",
        "//proto:common_js",
        "//proto:leaderboard_service_js",
        "//proto:season_service_js",
        "//truescrub/proto:profile_js",
        "//truescrub/proto:skill_groups_json",
    ],
)

ts_library(
    name = "matches_tab",
    srcs = ["MatchesTab.tsx"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//client/api:truescrub",
        "//client/components:error_state",
        "//client/components:loading_state",
        "//proto:profile_service_js",
    ],
)

ts_library(
    name = "team_records_tab",
    srcs = ["TeamRecordsTab.tsx"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//client/api:truescrub",
        "//client/components:error_state",
        "//client/components:loading_state",
        "//proto:profile_service_js",
    ],
)

ts_library(
    name = "profile_page",
    srcs = ["ProfilePage.tsx"],
    assets = [
        "ranks/cardboard_i.png",
        "ranks/cardboard_ii.png",
        "ranks/cardboard_iii.png",
        "ranks/cardboard_iv.png",
        "ranks/garb_salad.png",
        "ranks/legendary_wood.png",
        "ranks/low_key_dirty.png",
        "ranks/master_garbian.png",
        "ranks/master_garbian_elite.png",
        "ranks/plastic_elite.png",
        "ranks/plastic_i.png",
        "ranks/plastic_ii.png",
        "ranks/plastic_iii.png",
        "achievements/distinct_maps.png",
        "achievements/distinct_teammates.png",
        "achievements/multi_kill_rounds.png",
        "achievements/rounds_played.png",
        "achievements/seasons_played.png",
        "achievements/survived_losses.png",
        "achievements/total_headshots.png",
        "achievements/total_kills.png",
        "achievements/total_mvps.png",
        "achievements/zero_damage_rounds.png",
    ],
    visibility = ["//client:__subpackages__"],
    deps = [
        ":matches_tab",
        ":skill_group",
        ":team_records_tab",
        "//:node_modules/@bufbuild/protobuf",
        "//:node_modules/@connectrpc/connect-query",
        "//:node_modules/@tanstack/react-query",
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
        "//:node_modules/recharts",
        "//:node_modules/redux",
        "//client/api:seasons",
        "//client/api:truescrub",
        "//client/components:error_state",
        "//client/components:loading_state",
        "//proto:common_js",
        "//proto:profile_service_js",
        "//proto:season_service_js",
        "//truescrub/proto:achievements_json",
        "//truescrub/proto:profile_js",
        "//truescrub/proto:skill_groups_json",
    ],
)

ts_library(
    name = "not_found_page",
    srcs = ["NotFoundPage.tsx"],
    assets = [
        "chickens/404_chicken_1.png",
        "chickens/404_chicken_2.png",
        "chickens/404_chicken_3.png",
        "chickens/404_chicken_4.png",
    ],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//:node_modules/@types/react",
        "//:node_modules/@types/react-dom",
        "//:node_modules/react",
        "//:node_modules/react-dom",
        "//:node_modules/react-router-dom",
        "//client/components:globals",
    ],
)

ts_library(
    name = "leaderboard_page_test_lib",
    testonly = True,
    srcs = ["LeaderboardPage.test.ts"],
    tsconfig = "//:tsconfig_test",
    deps = [
        ":leaderboard_page",
        "//:node_modules/@types/jest",
        "//:node_modules/@types/node",
    ],
)

jest_test(
    name = "leaderboard_page_test",
    config = "//:jest.config.js",
    data = [
        ":leaderboard_page_test_lib",
        "//:jest_config",
        "//:node_modules/jest-environment-jsdom",
        "//client:file_mock",
        "//client:test_setup",
    ],
    node_modules = "//:node_modules",
)

ts_library(
    name = "profile_page_test_lib",
    testonly = True,
    srcs = ["ProfilePage.test.ts"],
    tsconfig = "//:tsconfig_test",
    deps = [
        ":profile_page",
        "//:node_modules/@types/jest",
        "//:node_modules/@types/node",
    ],
)

jest_test(
    name = "profile_page_test",
    config = "//:jest.config.js",
    data = [
        ":profile_page_test_lib",
        "//:jest_config",
        "//:node_modules/jest-environment-jsdom",
        "//client:file_mock",
        "//client:test_setup",
    ],
    node_modules = "//:node_modules",
)

ts_library(
    name = "skill_group",
    srcs = ["skill_group.ts"],
    visibility = ["//client:__subpackages__"],
    deps = [
        "//truescrub/proto:profile_js",
    ],
)

ts_library(
    name = "skill_group_test_lib",
    testonly = True,
    srcs = ["skill_group.test.ts"],
    tsconfig = "//:tsconfig_test",
    deps = [
        ":skill_group",
        "//:node_modules/@types/jest",
        "//:node_modules/@types/node",
        "//truescrub/proto:profile_js",
    ],
)

jest_test(
    name = "skill_group_test",
    config = "//:jest.config.js",
    data = [
        ":skill_group_test_lib",
        "//:jest_config",
        "//:node_modules/jest-environment-jsdom",
        "//client:file_mock",
        "//client:test_setup",
    ],
    node_modules = "//:node_modules",
)

ts_library(
    name = "accolades_page_test_lib",
    testonly = True,
    srcs = ["AccoladesPage.test.ts"],
    tsconfig = "//:tsconfig_test",
    deps = [
        ":accolades_page",
        "//:node_modules/@types/jest",
        "//:node_modules/@types/node",
    ],
)

jest_test(
    name = "accolades_page_test",
    config = "//:jest.config.js",
    data = [
        ":accolades_page_test_lib",
        "//:jest_config",
        "//:node_modules/jest-environment-jsdom",
        "//client:file_mock",
        "//client:test_setup",
    ],
    node_modules = "//:node_modules",
)

ts_library(
    name = "skill_groups_page_test_lib",
    testonly = True,
    srcs = ["SkillGroupsPage.test.ts"],
    tsconfig = "//:tsconfig_test",
    deps = [
        ":skill_groups_page",
        "//:node_modules/@types/jest",
        "//:node_modules/@types/node",
    ],
)

jest_test(
    name = "skill_groups_page_test",
    config = "//:jest.config.js",
    data = [
        ":skill_groups_page_test_lib",
        "//:jest_config",
        "//:node_modules/jest-environment-jsdom",
        "//client:file_mock",
        "//client:test_setup",
    ],
    node_modules = "//:node_modules",
)
