#!/usr/bin/env python3
"""Backward-compatibility shim — use ``cli.py`` (``homelab`` command) instead."""

import sys

from cli import main

if __name__ == "__main__":
    main(sys.argv[1:])
