TRUESCRUB_PAR	:= /opt/truescrub/truescrub.par

.PHONY: build
build:
	bazel build //truescrub:truescrub.par

.PHONY: deploy
deploy: build
	rsync -auvh --progress bazel-bin/truescrub/truescrub.par rumia:${TRUESCRUB_PAR}

.PHONY: recalculate
recalculate:
	ssh rumia TRUESCRUB_DATA_DIR=/var/db/truescrub ${TRUESCRUB_PAR} --recalculate

.PHONY: test
test:
	bazel test //tests:all

.PHONY: serve
serve:
	TRUESCRUB_DATA_DIR=${PWD}/data bazel run //truescrub -s

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
