load("@jq.bzl//:jq.bzl", "jq")

exports_files(["favicon.png"])

jq(
    name = "template_index",
    srcs = ["//client:app_bundle_metadata"],
    out = "index.html",
    args = [
        "--raw-output",
        "--rawfile",
        "template",
        "client/public/index.template.html",
    ],
    data = ["index.template.html"],
    filter_file = "template.jq",
    visibility = ["//client:__pkg__"],
)
