def _binary_toolchain_impl(ctx):
    return [platform_common.ToolchainInfo(
        info = struct(executable = ctx.executable.binary),
    )]

binary_toolchain = rule(
    implementation = _binary_toolchain_impl,
    attrs = {
        "binary": attr.label(
            mandatory = True,
            executable = True,
            allow_single_file = True,
            cfg = "exec",
        ),
    },
)

def _sws_impl(ctx):
    sws_bin = ctx.toolchains["//toolchains:sws_toolchain_type"].info.executable
    sws_link = ctx.actions.declare_file(ctx.label.name)
    ctx.actions.symlink(
        output = sws_link,
        target_file = sws_bin,
        is_executable = True,
    )
    return [
        DefaultInfo(
            executable = sws_link,
            runfiles = ctx.runfiles(files = [
                ctx.file.assets,
                ctx.file.config,
                sws_bin,
            ]),
        ),
        RunEnvironmentInfo(
            environment = {
                "SERVER_ROOT": ctx.file.assets.short_path,
                "SERVER_CONFIG_FILE": ctx.file.config.short_path,
                "SERVER_PORT": str(ctx.attr.port),
            } | ctx.attr.env,
        ),
    ]

sws = rule(
    implementation = _sws_impl,
    executable = True,
    toolchains = ["//toolchains:sws_toolchain_type"],
    attrs = {
        "assets": attr.label(mandatory = True, allow_single_file = True),
        "config": attr.label(allow_single_file = True, default = "//client:sws.toml"),
        "env": attr.string_dict(),
        "port": attr.int(default = 8080),
    },
)
