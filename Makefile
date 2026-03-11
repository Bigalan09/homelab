.PHONY: setup generate deploy test clean

DEVICE ?= router1
VENV   := .venv
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip

## setup: create virtualenv and install dependencies
setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

## generate: render configs for DEVICE (default: router1)
generate:
	PYTHONPATH=generator $(PYTHON) generator/generate.py $(DEVICE)

## generate-all: render configs for all devices in inventory
generate-all:
	PYTHONPATH=generator $(PYTHON) generator/generate.py all

## deploy: generate and deploy configs for DEVICE
deploy:
	./scripts/deploy.sh $(DEVICE)

## backup: download router configs locally for DEVICE
backup:
	./scripts/backup.sh $(DEVICE)

## rollback: restore last backup on DEVICE
rollback:
	./scripts/rollback.sh $(DEVICE)

## test: run tests
test:
	PYTHONPATH=generator $(VENV)/bin/pytest tests/ -v

## clean: remove generated build artifacts
clean:
	rm -rf build/

## help: show this help
help:
	@grep -E '^## ' Makefile | sed 's/^## //'
