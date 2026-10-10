#!/bin/bash
# Double-click this file in Finder to start Clique.
cd "$(dirname "$0")"
echo "Starting Clique... (close this window or press Ctrl+C to stop)"
( sleep 1.5 && open "http://localhost:3000" ) &
python3 server.py
