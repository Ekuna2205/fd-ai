#!/bin/sh
# FaceGuard AI: ./start.sh  (needs Python 3.11+)
cd "$(dirname "$0")" && exec python3 run.py "$@"
