"""Rules for extracting esbuild metadata files."""

def _esbuild_metadata_impl(ctx):
    metafile = None
    for f in ctx.attr.target[DefaultInfo].files.to_list():
        if f.basename.endswith("_metadata.json"):
            metafile = f
            break

    if not metafile:
        fail("Could not find _metadata.json in the outputs of %s" % ctx.attr.target.label)

    return DefaultInfo(files = depset([metafile]))

esbuild_metadata = rule(
    implementation = _esbuild_metadata_impl,
    attrs = {
        "target": attr.label(mandatory = True),
    },
)
