load("@rules_kustomize//kustomize:kustomize.bzl", "kustomization")

kustomization(
    name = "client",
    srcs = [
        "deployment.yaml",
        "kustomization.yaml",
        "service.yaml",
    ],
    visibility = ["//k8s/overlays/dev:__pkg__"],
)
