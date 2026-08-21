def get_bazel_deps(target):
    bazel_query = 'filter("^//", kind("source file", deps({0})) union buildfiles(deps({0})))'.format(target)
    result = local("bazel query '{0}'".format(bazel_query), quiet = True)
    return [
        line[3:] if line.startswith("//:") else line[2:].replace(":", "/")
        for line in str(result).splitlines()
    ]

def bazel_build(bazel_target, image_ref):
    build_cmd = """
    bazel run {0} -- \
          --repository="$EXPECTED_REGISTRY/{1}" \
          --tag="$EXPECTED_TAG"
    """.format(bazel_target, image_ref)
    custom_build(
        ref = image_ref,
        command = build_cmd,
        deps = get_bazel_deps(bazel_target),
        disable_push = True,
        skips_local_docker = True,
    )

def bazel_k8s(target):
    for f in get_bazel_deps(target):
        watch_file(f)
    bazel_cquery = 'bazel cquery "{0}" --output=files'.format(target)
    manifest = str(local(bazel_cquery, quiet = True)).strip()
    local("bazel build {0}".format(target))
    k8s_yaml(manifest)

bazel_build("//truescrub:push", "truescrub")
bazel_build("//client:push", "truescrub-client")
bazel_k8s("//k8s/overlays/dev:manifests")
