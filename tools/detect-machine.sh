#!/usr/bin/env bash
set -eu

nersc_host="${LQCD_DETECT_NERSC_HOST:-${NERSC_HOST:-}}"
case "$nersc_host" in
  perlmutter)
    printf '%s\n' perlmutter
    exit 0
    ;;
esac

detected_hostname="${LQCD_DETECT_HOSTNAME:-$(hostname 2>/dev/null || true)}"
case "$detected_hostname" in
  perlmutter.nersc.gov|saul.nersc.gov)
    printf '%s\n' perlmutter
    ;;
  *)
    printf '%s\n' unknown
    ;;
esac
