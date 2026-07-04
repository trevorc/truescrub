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

# Generate local dev certificates if they don't exist
if not os.path.exists("k8s/overlays/dev/tls.crt"):
    print("Generating local TLS certificates...")
    local([
        "openssl",
        "req",
        "-x509",
        "-nodes",
        "-days",
        "3650",
        "-newkey",
        "rsa:2048",
        "-keyout",
        "k8s/overlays/dev/tls.key",
        "-out",
        "k8s/overlays/dev/tls.crt",
        "-subj",
        "/CN=localhost",
        "-addext",
        "subjectAltName = DNS:localhost",
    ])

watch_file("k8s")
k8s_yaml(local("kustomize build --enable-helm k8s/overlays/dev"))
