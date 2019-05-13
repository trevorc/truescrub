.PHONY: build
build:
	docker build -t trevor3/truescrub:latest .

.PHONY: push
push:
	docker push trevor3/truescrub:latest
