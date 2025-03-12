#!/bin/sh

set -e
set -u

for python in \
  /usr/local/bin/python3.11 \
  /usr/bin/python3.11 \
  /usr/local/bin/python3.10 \
  /usr/bin/python3.10 \
  /usr/local/bin/python3.9 \
  /usr/bin/python3.9
do
  [ -f "$python" ] && break
done

if [ ! -f "$python" ]; then
  echo >&2 "error: suitable python not found"
fi

exec "$python" -S "$@"
