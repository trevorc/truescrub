load("@pip_requirements//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_library", "py_test")

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
    legacy_create_init = False,
    deps = [
        "//truescrub:matchmaking",
        "//truescrub:models",
        requirement("pytest"),
        requirement("trueskill"),
    ],
)

py_test(
    name = "test_models",
    srcs = ["test_models.py"],
    legacy_create_init = False,
    deps = [
        "//truescrub:models",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_state_parsing",
    srcs = ["test_state_parsing.py"],
    legacy_create_init = False,
    deps = [
        "//truescrub/statewriter:state_parsing",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_state_serialization",
    srcs = ["test_state_serialization.py"],
    data = ["sample_game_states.json"],
    legacy_create_init = False,
    deps = [
        "//truescrub/statewriter:state_parsing",
        "//truescrub/statewriter:state_serialization",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_segmented_log",
    srcs = ["test_segmented_log.py"],
    legacy_create_init = False,
    deps = [
        requirement("pytest"),
        "//truescrub/statewriter",
        "//truescrub/statewriter:segmented_log",
    ],
)

py_test(
    name = "test_state_writer",
    srcs = ["test_state_writer.py"],
    legacy_create_init = False,
    deps = [
        ":db_test_utils",
        "//truescrub/statewriter",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_highlights",
    srcs = ["test_highlights.py"],
    legacy_create_init = False,
    deps = [
        ":db_test_utils",
        "//truescrub:db",
        "//truescrub:highlights",
        "//truescrub:models",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_accolades",
    srcs = ["test_accolades.py"],
    legacy_create_init = False,
    deps = [
        "//truescrub:accolades",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_state_parser",
    srcs = ["test_state_parser.py"],
    legacy_create_init = False,
    deps = [
        "//truescrub:models",
        "//truescrub/updater",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_recalculate",
    srcs = ["test_recalculate.py"],
    legacy_create_init = False,
    deps = [
        "//truescrub:models",
        "//truescrub/updater",
        requirement("pytest"),
        requirement("trueskill"),
    ],
)

py_test(
    name = "test_api",
    srcs = ["test_api.py"],
    legacy_create_init = False,
    deps = [
        ":db_test_utils",
        "//truescrub:api",
        "//truescrub:db",
        "//truescrub:models",
        requirement("Flask"),
        requirement("pytest"),
    ],
)

py_test(
    name = "test_riegeli_loader",
    srcs = ["test_riegeli_loader.py"],
    legacy_create_init = False,
    deps = [
        ":db_test_utils",
        "//truescrub/proto:game_state_py_pb2",
        "//truescrub/statewriter",
        "//truescrub/statewriter:state_parsing",
        "//truescrub/tools:surgery",
        "//truescrub/updater:state_loader",
        "//truescrub/updater:recalculate",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_log_translator",
    srcs = ["test_log_translator.py"],
    legacy_create_init = False,
    deps = [
        ":db_test_utils",
        "//truescrub:db",
        "//truescrub/statewriter:segmented_log",
        "//truescrub/tools:log_translator",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_segmented_log_dir",
    srcs = ["test_segmented_log_dir.py"],
    legacy_create_init = False,
    deps = [
        "//truescrub/proto:game_state_py_pb2",
        "//truescrub/statewriter",
        "//truescrub/statewriter:segmented_log",
        "//truescrub/statewriter:state_parsing",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_integration_real_data",
    srcs = ["test_integration_real_data.py"],
    data = [
        "real_game_states_fixture.json",
        "sample_seasons.toml",
    ],
    legacy_create_init = False,
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
        requirement("Flask"),
        requirement("pytest"),
    ],
)

py_test(
    name = "test_teameval",
    srcs = ["test_teameval.py"],
    legacy_create_init = False,
    deps = [
        "//truescrub/tools:teameval",
        requirement("pytest"),
        requirement("trueskill"),
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
    ],
)
