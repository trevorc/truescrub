HOST		?= cirno
TRUESCRUB_ZIP	:= /opt/truescrub/truescrub.zip
TOOLS_ZIP	:= /opt/truescrub/tstools.zip

.PHONY: build
build:
	bazel build //:truescrub_zip //:dbsurgery_zip

.PHONY: deploy
deploy: build
	rsync -auvh --progress bazel-bin/truescrub/truescrub.zip ${HOST}:${TRUESCRUB_ZIP}
	rsync -auvh --progress bazel-bin/truescrub/tools/dbsurgery.zip ${HOST}:${TOOLS_ZIP}

.PHONY: recalculate
recalculate:
	ssh ${HOST} TRUESCRUB_DATA_DIR=/data/db/truescrub python3 ${TRUESCRUB_ZIP} --recalculate

.PHONY: test
test:
	bazel test //tests:all

.PHONY: serve
serve:
	TRUESCRUB_DATA_DIR=${PWD}/data bazel run //truescrub -- -s -p 3000

.PHONY: upload
upload:
	venv/bin/python3 setup.py sdist bdist_wheel
	twine upload dist/*

.PHONY: clean
clean:
	venv/bin/python3 setup.py clean --all

.PHONY: distclean
distclean: clean
	rm -Rf dist
	rm -Rf truescrub.egg-info
