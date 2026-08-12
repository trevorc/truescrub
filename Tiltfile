def get_bazel_deps(target):
    bazel_query = 'filter("^//", kind("source file", deps({0})) union buildfiles(deps({0})))'.format(target)
    result = local("bazel query '{0}'".format(bazel_query), quiet = True)
    return [
        line[2:].replace(":", "/")
        for line in str(result).splitlines()
    ]

def bazel_build(bazel_target, image_ref, registry):
    build_cmd = """
    bazel run {0} -- \
          --repository="$EXPECTED_REGISTRY/{1}" \
          --tag="$EXPECTED_TAG"
    """.format(bazel_target, image_ref)
    custom_build(
        ref = "{0}/{1}".format(registry, image_ref),
        command = build_cmd,
        deps = get_bazel_deps(bazel_target),
        disable_push = True,
        skips_local_docker = True,
    )

REGISTRY = "k3d-registry.localhost:5000"

bazel_build("//truescrub:push", "truescrub", REGISTRY)
bazel_build("//client:push", "truescrub-client", REGISTRY)

watch_file("k8s")
local("bazel build //k8s/overlays/dev")
k8s_yaml("bazel-bin/k8s/overlays/dev/manifests.yaml")
