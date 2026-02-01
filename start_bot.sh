#!/usr/bin/env bash
cd "$(dirname "$0")"

nix-shell shell.nix --run "ENVIRONMENT=prod python main.py"
