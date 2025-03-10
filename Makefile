HOST		?= cirno
TRUESCRUB_ZIP	:= /opt/truescrub/truescrub.zip
TOOLS_ZIP	:= /opt/truescrub/tstools.zip

# Bazel setup
.PHONY: bazel-setup
bazel-setup:
	./scripts/setup_bazel.sh

.PHONY: build-zip
build-zip: bazel-setup protos
	bazel build --config=local //:truescrub_zip //:dbsurgery_zip

.PHONY: deploy
deploy: build-zip
	rsync -avh --progress "$(shell bazel cquery --output=files //:truescrub_zip)" ${HOST}:${TRUESCRUB_ZIP}
	rsync -avh --progress "$(shell bazel cquery --output=files //:dbsurgery_zip)" ${HOST}:${TOOLS_ZIP}

.PHONY: recalculate
recalculate:
	ssh ${HOST} TRUESCRUB_DATA_DIR=/data/db/truescrub python3 ${TRUESCRUB_ZIP} --recalculate

.PHONY: test
test: bazel-setup protos
	bazel test //tests:tests

.PHONY: build
build: bazel-setup protos
	bazel build //truescrub

.PHONY: serve
serve: bazel-setup protos
	TRUESCRUB_DATA_DIR=${PWD}/data bazel run --config=local //truescrub -- -s -p 3000

# Linting and code quality
.PHONY: setup
setup:
	python -m venv .venv || true
	. .venv/bin/activate && pip install -r requirements.in
	./scripts/setup_bazel.sh

.PHONY: setup-dev
setup-dev:
	pip install -r requirements-dev.in

.PHONY: protos
protos:
	./scripts/regen_protos.sh

.PHONY: lint
lint: setup-dev
	ruff check .

.PHONY: lint-fix
lint-fix: setup-dev
	ruff check --fix .
	
.PHONY: format
format: setup-dev
	black .
	isort .

.PHONY: typecheck
typecheck: setup-dev protos
	mypy truescrub

.PHONY: quality
quality: lint typecheck
