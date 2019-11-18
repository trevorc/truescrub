.PHONY: build
build:
	docker build -t trevor3/truescrub:latest .

.PHONY: push
push:
	docker push trevor3/truescrub:latest

.PHONY: deploy
deploy:
	ssh rumia "sh -c 'cd services && docker-compose pull truescrub && docker-compose up -d --force-recreate truescrub truescrub-updater nginx'"

.PHONY: recalculate
recalculate:
	ssh rumia docker exec services_truescrub_1 python -m truescrub --recalculate
