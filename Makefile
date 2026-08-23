.PHONY: install test lint cli list tui serve site gui-build

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

lint:
	python -m ruff check portway tests

cli:
	python -m portway scan --profile quick --host 127.0.0.1

list:
	python -m portway list

tui:
	python -m portway tui

serve:
	python -m portway serve --bind 0.0.0.0 --port 5050

site:
	python -m http.server 4173 --directory website

gui-build:
	cd gui && NPM_CONFIG_CACHE=/tmp/portway-npm-cache npm ci && NPM_CONFIG_CACHE=/tmp/portway-npm-cache npm run build
	rm -rf gui/node_modules
