load("@rules_kustomize//kustomize:kustomize.bzl", "kustomization", "kustomized_resources")

genrule(
    name = "generate_tls_certs",
    outs = [
        "tls.crt",
        "tls.key",
    ],
    cmd = "$(location @openssl//:openssl) req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout $(location tls.key) -out $(location tls.crt) -subj '/CN=localhost' -addext 'subjectAltName = DNS:localhost'",
    tools = ["@openssl"],
)

kustomization(
    name = "dev",
    srcs = [
        "gateway.yaml",
        "gatewayclass.yaml",
        "kustomization.yaml",
        "namespace.yaml",
        "tls.crt",
        "tls.key",
    ],
    requires_helm = True,
    deps = [
        "//k8s/apps/client",
        "//k8s/apps/truescrub",
    ],
)

kustomized_resources(
    name = "manifests",
    kustomization = ":dev",
    load_restrictor = "None",
)
