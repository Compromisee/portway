.PHONY: install test lint cli site

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

lint:
	python -m ruff check portway tests

cli:
	python -m portway --cli --profile quick --host 127.0.0.1

site:
	python -m http.server 4173 --directory website
