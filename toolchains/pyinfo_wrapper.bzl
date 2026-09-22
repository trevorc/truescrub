load("@aspect_rules_py//py:defs.bzl", AspectPyInfo = "PyInfo")
load("@rules_python//python:py_info.bzl", LegacyPyInfo = "PyInfo")

def _pyinfo_wrapper_impl(ctx):
    aspect_info = ctx.attr.target[AspectPyInfo]

    return [
        LegacyPyInfo(
            transitive_sources = aspect_info.transitive_sources,
            imports = aspect_info.imports,
            has_py2_only_sources = False,
            has_py3_only_sources = True,
        ),
        ctx.attr.target[DefaultInfo],
    ]

pyinfo_wrapper = rule(
    implementation = _pyinfo_wrapper_impl,
    attrs = {"target": attr.label(mandatory = True, providers = [AspectPyInfo])},
    provides = [LegacyPyInfo],
)
