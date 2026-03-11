.PHONY: setup list validate generate generate-all status deploy backup rollback test clean help

DEVICE ?= flint2
VENV   := .venv
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip

## setup: create virtualenv and install dependencies
setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

## list: list available devices discovered from docs/devices/ directory
list:
	PYTHONPATH=generator $(PYTHON) generator/cli.py list

## validate: validate configs for DEVICE (default: flint2); use DEVICE=all for all
validate:
	PYTHONPATH=generator $(PYTHON) generator/cli.py validate $(DEVICE)

## generate: render configs for DEVICE (default: flint2)
generate:
	PYTHONPATH=generator $(PYTHON) generator/cli.py generate $(DEVICE)

## generate-all: render configs for all devices in docs/inventory
generate-all:
	PYTHONPATH=generator $(PYTHON) generator/cli.py generate all

## status: show per-device build status
status:
	PYTHONPATH=generator $(PYTHON) generator/cli.py status

## deploy: check build files exist and deploy configs for DEVICE
deploy:
	PYTHONPATH=generator $(PYTHON) generator/cli.py deploy $(DEVICE)

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
