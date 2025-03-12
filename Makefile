HOST		?= truescrub.life
TRUESCRUB_ZIP	:= /opt/truescrub/truescrub.zip
TOOLS_ZIP	:= /opt/truescrub/tstools.zip

.PHONY: build
build:
	bazel build //:truescrub_zip //:dbsurgery_zip

.PHONY: deploy
deploy: build
	rsync -avh --progress "$(shell bazel cquery --output=files //:truescrub_zip)" ${HOST}:${TRUESCRUB_ZIP}
	rsync -avh --progress "$(shell bazel cquery --output=files //:dbsurgery_zip)" ${HOST}:${TOOLS_ZIP}

.PHONY: recalculate
recalculate:
	ssh ${HOST} TRUESCRUB_DATA_DIR=/data/db/truescrub python3 ${TRUESCRUB_ZIP} --recalculate

.PHONY: test
test:
	bazel test //tests:all

.PHONY: serve
serve:
	TRUESCRUB_DATA_DIR=${PWD}/data bazel run //truescrub -- -s -p 3000
