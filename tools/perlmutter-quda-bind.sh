#!/usr/bin/env bash
#
# Rank binding for QUDA on Perlmutter GPU nodes, at EXACTLY four ranks per node.
#
# SCOPE: machine AND application. This script is two halves with different
# scopes, and reusing it under another application means reusing only one of
# them:
#
#   CPU cores, memory domain, NIC mapping   MACHINE-scoped. Perlmutter GPU node
#                                           topology. Any application running
#                                           four ranks per node can use this.
#   no accelerator binding                  APPLICATION-scoped, and specific to
#                                           QUDA. It is not a machine fact and
#                                           not a general good practice.
#
# The second half is the one that does not travel. QUDA derives its device from
# a rank index counted across the node, so restricting visibility breaks it --
# but an application that selects its device differently may want per-rank
# accelerator binding, and would be wrong to inherit this omission just because
# the CPU half suited it. **Do not adopt this script for a different application
# without deciding the accelerator half again from that application's own device
# selection.**
#
# USAGE, as a wrapper around the application in the parallel launcher's argv:
#
#     <parallel-launcher> ... "$handbook/tools/perlmutter-bind.sh" ./application
#
# THE ALLOCATION ARITHMETIC, which is the way this script is usually broken.
# It names CPU indices up to 127, so the job's per-node cpuset must contain at
# least 128 logical CPUs, or every rank dies inside `numactl` before the
# application is ever executed:
#
#     libnuma: Warning: cpu argument 15,64-79 out of range
#
# With four tasks per node that means the per-task CPU request must be 32
# (4 x 32 = 128). The tell, when it is wrong, is that ONLY the upper portion of
# each range is ever objected to; the fix is the allocation, not this script.
# conventions/batch-scripts.md owns the general rule.
#
# The per-task CPU request is NOT the OpenMP thread count. On this node each
# core carries two hardware threads, so the thread count is 16 while the per-task
# request is 32. Setting them equal is the natural and wrong move, and it yields
# a cpuset exactly half the size this script addresses.
#
# FOUR RANKS PER NODE, and the assumption is silent if violated. `lrank` is taken
# modulo four, so at eight tasks per node ranks 0 and 4 receive an identical
# cpuset, memory domain and NIC with no warning at all. Check the task count
# before reusing this at another rank layout.
#
# DO NOT ADD ACCELERATOR BINDING HERE. Restricting device visibility per rank
# aborts every local rank above the first under QUDA, and the apparent workaround
# is worse than the problem; software/quda/internals/rank-placement.md owns that
# mechanism and is why the Perlmutter stack records accelerator binding as
# disabled rather than merely unused.
#
# Evidence: operator. Run by the operator on Perlmutter at 1, 2 and 216 nodes.
# The executable logic below is unmodified from that tested script; everything
# added here is comment.

# Bash Strict Mode
set -euo pipefail

# Local rank on the node
lrank=$(( $SLURM_LOCALID % 4 ))

# Print what each rank will run
echo "rank=$SLURM_PROCID localid=$SLURM_LOCALID lrank=$lrank cmd: $*" >&2

# GPU and NIC binding
export MPICH_OFI_NIC_POLICY="USER"
export MPICH_OFI_NIC_MAPPING="0:3;1:2;2:1;3:0"

# CPU and memory binding
case "$lrank" in
 0) exec numactl --physcpubind=0-15,64-79    --membind=0 "$@" ;;
 1) exec numactl --physcpubind=16-31,80-95   --membind=1 "$@" ;;
 2) exec numactl --physcpubind=32-47,96-111  --membind=2 "$@" ;;
 3) exec numactl --physcpubind=48-63,112-127 --membind=3 "$@" ;;
esac
