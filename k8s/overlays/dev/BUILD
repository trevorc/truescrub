load("@rules_helm//helm:defs.bzl", "helm_template")
load("@rules_kustomize//kustomize:kustomize.bzl", "kustomization", "kustomized_resources")

genrule(
    name = "generate_tls_certs",
    outs = [
        "tls.crt",
        "tls.key",
    ],
    cmd = "$(location @openssl//:openssl) req -config /dev/null -x509 -nodes -days 3650 -newkey rsa:2048 -keyout $(location tls.key) -out $(location tls.crt) -subj '/CN=localhost' -addext 'subjectAltName = DNS:localhost'",
    tools = ["@openssl"],
)

helm_template(
    name = "gateway_helm",
    chart = "@envoy_gateway_chart//:gateway-helm",
    opts = [
        "--name-template=eg",
        "--namespace=envoy-gateway-system",
        "--include-crds",
    ],
)

kustomization(
    name = "dev",
    srcs = [
        "gateway.yaml",
        "gatewayclass.yaml",
        "kustomization.yaml",
        "namespace.yaml",
        ":gateway_helm",
        ":tls.crt",
        ":tls.key",
    ],
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
