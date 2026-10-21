#!/bin/sh
exec flock -w 900 /tmp/hunter.lock .venv/bin/python -u "$@"
