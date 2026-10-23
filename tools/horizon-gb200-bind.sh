#!/bin/bash
#
# Rank binding for one Horizon gpu-gb200 board (GB200 NVL4: 4 GPUs, 2 Grace sockets of
# 72 cores, 4 InfiniBand HCAs) at EXACTLY four ranks per node.
#
# SCOPE: machine AND application, in two halves with different reach.
#
#   CPU cores, memory domain, NIC     MACHINE-scoped: local rank n gets cores 36n..36n+35
#                                     (NUMA n/2) and HCA mlx5_0, mlx5_1, mlx5_4, mlx5_5.
#   GPU visibility                    APPLICATION-scoped. By default each rank sees only GPU
#                                     n (CUDA_VISIBLE_DEVICES=n), which Grid, Hadrons and
#                                     HadronsMILC require: Grid always selects the first
#                                     visible device (software/grid/runtime-environment.md).
#                                     QUDA instead picks its device from the node-local rank
#                                     and needs all four visible: set
#                                     SELECT_GPU_ALL_VISIBLE=1 for MILC/QUDA executables
#                                     (software/quda/internals/rank-placement.md).
#
# USAGE, as a wrapper around the application in the launcher's argv, under srun:
#
#     #SBATCH --ntasks-per-node=4 --cpus-per-task=36
#     srun --cpu-bind=none "$handbook/tools/horizon-gb200-bind.sh" ./application ...
#
# --cpu-bind=none stops srun's own binding from competing with numactl. The script names
# CPU indices up to 143, so the job's per-node cpuset must hold all 144 cores
# (4 tasks x 36 CPUs); a smaller cpuset kills every rank inside numactl before the
# application starts (conventions/batch-scripts.md owns the rule). OMP_NUM_THREADS is set to
# 36 (override with SELECT_GPU_OMP), because TACC's environment exports 1.
#
# FOUR RANKS PER NODE, and the assumption is not checked: a fifth local rank would index
# past the HCA list and past core 143.
#
# Evidence, Grid/HadronsMILC half: an in-job placement probe under srun on one board showed
# local rank n with CUDA_VISIBLE_DEVICES=n, cores 36n..36n+35 and UCX_NET_DEVICES as above,
# and Grid reported a node communicator of size 4; Grid, Hadrons and HadronsMILC validation
# runs on 1 and 4 GPUs used this script unchanged. The membind was not observed (the probe's
# Mems_allowed shows the cpuset, not numactl's policy). The QUDA mode
# (SELECT_GPU_ALL_VISIBLE=1) and multi-node use were not run with this script. The
# executable logic below is unmodified from that tested wrapper; everything above it is
# comment.

APP="$*"

LOCAL_RANK=${OMPI_COMM_WORLD_LOCAL_RANK:-${SLURM_LOCALID:-0}}
GLOBAL_RANK=${OMPI_COMM_WORLD_RANK:-${SLURM_PROCID:-0}}

HCAS=(mlx5_0 mlx5_1 mlx5_4 mlx5_5)
NUMA_NODE=$(( LOCAL_RANK / 2 ))
FIRST_CORE=$(( LOCAL_RANK * 36 ))
CPU_LIST=${FIRST_CORE}-$(( FIRST_CORE + 35 ))

# QUDA (MILC) picks its device from the node-local rank itself and needs all
# 4 GPUs visible: set SELECT_GPU_ALL_VISIBLE=1 for MILC/QUDA executables.
if [ -z "${SELECT_GPU_ALL_VISIBLE}" ]; then
  export CUDA_VISIBLE_DEVICES=${LOCAL_RANK}
fi
export UCX_NET_DEVICES=${HCAS[$LOCAL_RANK]}:1
# one rank per 36 cores; Slurm/TACC pre-set OMP_NUM_THREADS (often 1), so override it
export OMP_NUM_THREADS=${SELECT_GPU_OMP:-36}

if [ "${GLOBAL_RANK}" -eq 0 ]; then
  echo "select_gpu: local rank ${LOCAL_RANK} -> GPU ${CUDA_VISIBLE_DEVICES}, ${UCX_NET_DEVICES}, NUMA ${NUMA_NODE}, cpus ${CPU_LIST}, OMP_NUM_THREADS=${OMP_NUM_THREADS}"
  echo "select_gpu: executing $APP"
fi

exec numactl --physcpubind=${CPU_LIST} --membind=${NUMA_NODE} "$@"
