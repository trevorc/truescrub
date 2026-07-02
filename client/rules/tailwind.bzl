load("@aspect_rules_js//js:defs.bzl", "js_run_binary")

def tailwind_css(name, srcs, input = None, **kwargs):
    """Compiles Tailwind CSS by scanning content files for class names.

    Args:
        name: Target name.
        srcs: Labels of files to scan for class names (e.g. esbuild bundles).
        input: Optional CSS file to use as the entry point (e.g. "style.css").
        **kwargs: Additional arguments to pass to js_run_binary.
    """
    output = name + ".css"

    run_srcs = list(srcs)
    args = []

    if input:
        run_srcs.append(input)
        args.extend(["--input", input])

    args.extend([
        "--output",
        output,
        "--minify",
    ])

    js_run_binary(
        name = name,
        tool = "//client:tailwindcss",
        srcs = run_srcs,
        outs = [output],
        chdir = native.package_name(),
        args = args,
        silent_on_success = True,
        **kwargs
    )
