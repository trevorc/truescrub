.PHONY: build
build:
	docker build -t trevor3/truescrub:latest .

.PHONY: push
push:
	docker push trevor3/truescrub:latest

.PHONY: deploy
deploy:
	ssh rumia "sh -c 'cd services && docker-compose pull truescrub && docker-compose up -d --force-recreate truescrub truescrub-updater && docker-compose restart nginx'"

.PHONY: recalculate
recalculate:
	ssh rumia docker exec services_truescrub_1 python -m truescrub --recalculate

.PHONY: serve
serve:
	waitress-serve --port 9000 truescrub.api:app

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
