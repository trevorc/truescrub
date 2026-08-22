load("@aspect_rules_js//js:providers.bzl", "JsInfo")

_TAILWINDCSS_TOOLCHAIN = "//client/toolchains:tailwindcss_toolchain_type"

def _tailwind_css_impl(ctx):
    tailwind_bin = ctx.toolchains[_TAILWINDCSS_TOOLCHAIN].info.executable

    output = ctx.actions.declare_file(ctx.attr.name + ".css")

    args = ctx.actions.args()
    if ctx.file.input:
        args.add("-i", ctx.file.input.path)
    args.add("--output", output.path)
    args.add("--minify")

    transitive_inputs = depset(transitive = [
        dep[JsInfo].transitive_sources if JsInfo in dep else dep[DefaultInfo].files
        for dep in ctx.attr.srcs
    ])

    run_inputs = [transitive_inputs]
    if ctx.file.input:
        run_inputs.append(depset([ctx.file.input]))

    ctx.actions.run(
        outputs = [output],
        inputs = depset(transitive = run_inputs),
        executable = tailwind_bin,
        arguments = [args],
        progress_message = "Compiling Tailwind CSS %s" % ctx.label,
    )

    return [DefaultInfo(files = depset([output]))]

tailwind_css_rule = rule(
    implementation = _tailwind_css_impl,
    toolchains = [_TAILWINDCSS_TOOLCHAIN],
    attrs = {
        "srcs": attr.label_list(allow_files = True),
        "input": attr.label(allow_single_file = [".css"]),
    },
)

def _tailwind_css_macro_impl(name, visibility, **kwargs):
    tailwind_css_rule(
        name = name,
        visibility = visibility,
        **kwargs
    )

tailwind_css = macro(
    implementation = _tailwind_css_macro_impl,
    inherit_attrs = tailwind_css_rule,
)
