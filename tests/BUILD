load("@aspect_rules_py//py:defs.bzl", "py_library", "py_test")

py_library(
    name = "db_test_utils",
    srcs = [
        "__init__.py",
        "db_test_utils.py",
    ],
    data = ["sample_seasons.toml"],
    deps = [
        "//truescrub:db",
        "//truescrub:models",
        "//truescrub/updater",
    ],
)

py_test(
    name = "test_matchmaking",
    srcs = ["test_matchmaking.py"],

    deps = [
        "//truescrub:matchmaking",
        "//truescrub:models",
        "@pypi//pytest",
        "@pypi//trueskill",
    ],
)

py_test(
    name = "test_models",
    srcs = ["test_models.py"],

    deps = [
        "//truescrub:models",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_state_parsing",
    srcs = ["test_state_parsing.py"],

    deps = [
        "//truescrub/statewriter:state_parsing",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_state_serialization",
    srcs = ["test_state_serialization.py"],
    data = ["sample_game_states.json"],

    deps = [
        "//truescrub/statewriter:state_parsing",
        "//truescrub/statewriter:state_serialization",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_segmented_log",
    srcs = ["test_segmented_log.py"],

    deps = [
        "@pypi//pytest",
        "//truescrub/statewriter",
        "//truescrub/statewriter:segmented_log",
    ],
)

py_test(
    name = "test_state_writer",
    srcs = ["test_state_writer.py"],

    deps = [
        ":db_test_utils",
        "//truescrub/statewriter",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_highlights",
    srcs = ["test_highlights.py"],

    deps = [
        ":db_test_utils",
        "//truescrub:db",
        "//truescrub:highlights",
        "//truescrub:models",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_accolades",
    srcs = ["test_accolades.py"],

    deps = [
        "//truescrub:accolades",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_state_parser",
    srcs = ["test_state_parser.py"],

    deps = [
        "//truescrub:models",
        "//truescrub/updater",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_recalculate",
    srcs = ["test_recalculate.py"],

    deps = [
        "//truescrub:models",
        "//truescrub/updater",
        "@pypi//pytest",
        "@pypi//trueskill",
    ],
)

py_test(
    name = "test_api",
    srcs = ["test_api.py"],

    deps = [
        ":db_test_utils",
        "//truescrub:api",
        "//truescrub:db",
        "//truescrub:models",
        "@pypi//flask",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_riegeli_loader",
    srcs = ["test_riegeli_loader.py"],

    deps = [
        ":db_test_utils",
        "//truescrub/proto:game_state_py_pb2",
        "//truescrub/statewriter",
        "//truescrub/statewriter:state_parsing",
        "//truescrub/tools:surgery",
        "//truescrub/updater:state_loader",
        "//truescrub/updater:recalculate",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_log_translator",
    srcs = ["test_log_translator.py"],

    deps = [
        ":db_test_utils",
        "//truescrub:db",
        "//truescrub/statewriter:segmented_log",
        "//truescrub/tools:log_translator",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_segmented_log_dir",
    srcs = ["test_segmented_log_dir.py"],

    deps = [
        "//truescrub/proto:game_state_py_pb2",
        "//truescrub/statewriter",
        "//truescrub/statewriter:segmented_log",
        "//truescrub/statewriter:state_parsing",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_integration_real_data",
    srcs = ["test_integration_real_data.py"],
    data = [
        "real_game_states_fixture.json",
        "sample_seasons.toml",
    ],

    deps = [
        ":db_test_utils",
        "//truescrub:api",
        "//truescrub:db",
        "//truescrub:highlights",
        "//truescrub:models",
        "//truescrub/statewriter",
        "//truescrub/updater",
        "//truescrub/updater:state_loader",
        "//truescrub/updater:recalculate",
        "@pypi//flask",
        "@pypi//pytest",
    ],
)

py_test(
    name = "test_teameval",
    srcs = ["test_teameval.py"],

    deps = [
        "//truescrub/tools:teameval",
        "@pypi//pytest",
        "@pypi//trueskill",
    ],
)

py_test(
    name = "test_integration",
    srcs = ["test_integration.py"],

    deps = [
        "//truescrub:models",
        "//truescrub:matchmaking",
        "//truescrub/updater:recalculate",
        "@pypi//pytest",
    ],
)

test_suite(
    name = "tests",
    tests = [
        "test_teameval",
        "test_accolades",
        "test_api",
        "test_highlights",
        "test_integration_real_data",
        "test_log_translator",
        "test_matchmaking",
        "test_models",
        "test_recalculate",
        "test_riegeli_loader",
        "test_state_parser",
        "test_state_serialization",
        "test_segmented_log",
        "test_segmented_log_dir",
        "test_integration",
    ],
)
