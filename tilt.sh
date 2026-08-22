#!/bin/sh
set -eu

./bootstrap-k3d.sh truescrub

case "${1:-}" in
  up|down|ci|doctor)
    set -- "$@" --context="k3d-truescrub" ;;
esac

exec tilt "$@"
