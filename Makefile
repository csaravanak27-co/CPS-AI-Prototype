PYTHON ?= python

.PHONY: test self-check package docker-run

test:
	QT_QPA_PLATFORM=offscreen $(PYTHON) -m pytest -v

self-check:
	QT_QPA_PLATFORM=offscreen $(PYTHON) app.py --self-check

package:
	$(PYTHON) scripts/package_release.py

docker-run:
	docker build -t cps-ai:1.0.0 .
	docker run --rm -p 8899:8899 cps-ai:1.0.0
