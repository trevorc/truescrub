HOST		?= cirno
TRUESCRUB_PAR	:= /opt/truescrub/truescrub.par
TOOLS_PAR	:= /opt/truescrub/tstools.par

.PHONY: build
build:
	bazel build //truescrub:truescrub.par //truescrub/tools:dbsurgery.par

.PHONY: deploy
deploy: build
	rsync -auvh --progress bazel-bin/truescrub/truescrub.par ${HOST}:${TRUESCRUB_PAR}
	rsync -auvh --progress bazel-bin/truescrub/tools/dbsurgery.par ${HOST}:${TOOLS_PAR}

.PHONY: recalculate
recalculate:
	ssh ${HOST} TRUESCRUB_DATA_DIR=/data/db/truescrub ${TRUESCRUB_PAR} --recalculate

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
