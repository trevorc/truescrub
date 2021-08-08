.PHONY: build
build:
	bazel build //truescrub:truescrub.par

.PHONY: deploy
deploy: build
	scp bazel-bin/truescrub/truescrub.par rumia:/opt/truescrub/
	ssh rumia sudo systemctl restart truescrub

.PHONY: recalculate
recalculate:
	ssh rumia docker exec services_truescrub_1 python -m truescrub --recalculate

.PHONY: serve
serve:
	TRUESCRUB_DATA_DIR=data bazel run //truecrub -s

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
