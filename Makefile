HOST			?= truescrub.life
TRUESCRUB_ZIP_SRC	:= $(shell bazel --bazelrc=deploy.bazelrc cquery --output=files //:truescrub_zip)
DBSURGERY_ZIP_SRC	:= $(shell bazel --bazelrc=deploy.bazelrc cquery --output=files //:dbsurgery_zip)
TRUESCRUB_ZIP_DEST	:= /opt/truescrub/truescrub.zip
DBSURGERY_ZIP_DEST	:= /opt/truescrub/dbsurgery.zip

.PHONY: build
build: ${TRUESCRUB_ZIP_SRC} ${DBSURGERY_ZIP_SRC}

${TRUESCRUB_ZIP_SRC}:
	bazel --bazelrc=deploy.bazelrc build //:truescrub_zip

${DBSURGERY_ZIP_SRC}:
	bazel --bazelrc=deploy.bazelrc build //:dbsurgery_zip

.PHONY: deploy deploy-truescrub deploy-dbsurgery
deploy: deploy-truescrub deploy-dbsurgery
deploy-truescrub: ${TRUESCRUB_ZIP_SRC}
	rsync -avh --progress "$<" ${HOST}:${TRUESCRUB_ZIP_DEST}
deploy-dbsurgery: ${DBSURGERY_ZIP_SRC}
	rsync -avh --progress "$<" ${HOST}:${DBSURGERY_ZIP_DEST}

.PHONY: recalculate
recalculate:
	ssh ${HOST} TRUESCRUB_DATA_DIR=/var/db/truescrub python3 ${TRUESCRUB_ZIP_DEST} --recalculate

.PHONY: test
test:
	bazel test //tests:all

.PHONY: serve
serve: ${TRUESCRUB_ZIP_SRC}
	TRUESCRUB_DATA_DIR=${PWD}/data python3 "$<" -s -p 3000
