#!/usr/bin/env bash
set -eu

nersc_host="${LQCD_DETECT_NERSC_HOST:-${NERSC_HOST:-}}"
case "$nersc_host" in
  perlmutter)
    printf '%s\n' perlmutter
    exit 0
    ;;
esac

detected_hostname="${LQCD_DETECT_HOSTNAME:-$(hostname -f 2>/dev/null || hostname 2>/dev/null || true)}"
case "$detected_hostname" in
  perlmutter.nersc.gov|saul.nersc.gov)
    printf '%s\n' perlmutter
    ;;
  frontier.olcf.ornl.gov|login[0-9][0-9].frontier.olcf.ornl.gov|frontier[0-9]*)
    printf '%s\n' frontier
    ;;
  *)
    printf '%s\n' unknown
    ;;
esac
