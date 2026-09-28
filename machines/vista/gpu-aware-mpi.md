---
title: GPU-aware MPI on Vista — which UCX Open MPI really loads, and the UCX 1.17 gdr_copy registration failure
summary: TACC's Open MPI builds are each linked to one UCX version, which need not be the one the loaded ucx module names; the gcc14/cuda12 openmpi/5.0.5 build is pinned to UCX 1.17.0, which fails to register GPU memory with the HCA whenever the gdr_copy transport is present, so GPUDirect RDMA breaks for small device-memory messages. UCX 1.18 and later do not fail; openmpi/5.0.9 (UCX 1.20.0) is validated across nodes. Includes a one-node GDR check that needs no batch job.
scope: [machine:vista]
load_when: Choosing an MPI module for GPU work on Vista, diagnosing an ibv_reg_dmabuf_mr or "failed to register address ... (cuda)" error, deciding whether GPUDirect RDMA was actually in force, or checking GDR on one node before spending a multi-node allocation.
evidence: experiment
sources:
  - https://docs.nvidia.com/nvidia-hpc-x-software-toolkit-rev-2-19-0.pdf
  - https://github.com/openucx/ucx/releases/tag/v1.18.0
  - operator's screened diagnostic-rig records
observed: "2026-09-28"
observed_on:
  machine: vista
  node_type: gpu-gh200
  toolchain:
    nvidia-driver: "590.48.01"
    ucx: "1.17.0, 1.18.0, 1.20.0"
    openmpi: "5.0.5 (gcc14/cuda12), 5.0.9 (nvidia26/cuda13)"
---

# GPU-aware MPI on Vista

## The module list does not say which UCX MPI uses

Each TACC Open MPI build is linked to one UCX installation. Loading an Open MPI module also
loads a `ucx` module, but that module need not be the one the library uses. The
`gcc/14.2.0 cuda/12.8 openmpi/5.0.5` build was configured against UCX 1.17.0 and carries
**`DT_RPATH`** to it, which the dynamic loader searches before `LD_LIBRARY_PATH`; the
environment meanwhile lists `ucx/1.20.0`. The `nvidia/26.1 cuda/13.1 openmpi/5.0.9` build
carries `RUNPATH` to UCX 1.20.0 and agrees with its environment. Other builds on the system
are wired to 1.18.x or 1.19.x.

So **record the UCX a run used from the run, not from `module list`**: `ldd` on `libmpi.so`
before the job, and `UCX_LOG_LEVEL=info`, which makes UCX print
`Version <x> (loaded from <path>)` at start-up, inside it.

## UCX 1.17.0 with `gdr_copy` cannot register GPU memory here

**Symptom.** A GPU-aware exchange from device memory aborts with

```text
ib_md.c  UCX ERROR ibv_reg_dmabuf_mr(address=..., length=..., access=0xf) failed: Invalid argument
ucp_mm.c UCX ERROR failed to register address ... (cuda) ... on md[..]=mlx5_0: ... (md supports: host)
pml_ucx.c Error: ucx send failed: Input/output error
```

and then an MPI or QMP abort. QUDA's native multi-rank tests show it with
`QUDA_ENABLE_GDR=1`; the reported lengths are whole CUDA allocations, not message sizes.

**What triggers it** `[experiment]`, established with one variable moved at a time on one
node, sending over `mlx5_0` between two ranks:

| UCX | Transports | Result |
|---|---|---|
| 1.17.0 | `rc_mlx5,ud_mlx5,cuda_copy` | pass; device memory moves by registered zero-copy |
| 1.17.0 | the same plus `gdr_copy` | **fail**, the error above |
| 1.17.0 | the same plus `gdr_copy`, `UCX_CUDA_COPY_DMABUF=no` | pass, but staged through host memory |
| 1.18.0 | the same plus `gdr_copy` | pass |
| 1.20.0 | UCX default list (includes `gdr_copy`) | pass across four nodes, GPU-to-GPU zero-copy |

UCX's default transport list includes `gdr_copy`, and `gdrdrv` is loaded on these nodes, so
the failing row is what a job gets by default under `openmpi/5.0.5`. It matches NVIDIA's
HPC-X 2.19 known issue for the same error and workaround. The node itself is not at fault:
registering `cudaMalloc` memory with `mlx5_0` directly succeeds through dmabuf and through
`nvidia_peermem`, both of which are loaded. Why `gdr_copy`'s presence breaks the later
dmabuf registration in 1.17 is **not established**. Separately, UCX 1.17 checks only the
legacy `nv_peer_mem` interface for a peer-memory driver and does not recognise
`nvidia_peermem`, the module these nodes load; 1.18 adds that check.

**Why message size decides whether a run notices.** The failure needs a protocol that
registers the GPU buffer. With UCX 1.17 that is the eager zero-copy band for small
device-memory messages — up to about 8 KB, and multi-fragment eager up to about 13 KB on
these nodes — and a registered rendezvous. QUDA's small test lattices fall there. MILC-sized
halos (tens to hundreds of KB) completed, but the protocol tables at that size recorded only
host-sourced rendezvous fetches, so those runs were not GPU-to-GPU either. A run that passes
is therefore not evidence that GDR worked; see below.

## What to do

- **Use a validated stack built on `openmpi/5.0.9`** (UCX 1.20.0):
  [`stacks/quda-cuda13-milc-cg-2026q3/notes.md`](stacks/quda-cuda13-milc-cg-2026q3/notes.md)
  and
  [`stacks/milc-cuda13-quda-ks-spectrum-2026q3/notes.md`](stacks/milc-cuda13-quda-ks-spectrum-2026q3/notes.md).
  GDR works there with UCX's default transports.
- **On an `openmpi/5.0.5` build, set `UCX_TLS=^gdr_copy`.** It removes the failing
  combination and kept registered zero-copy in the one-node check above. It has not been run
  across nodes or timed, and it gives up `gdr_copy`'s small-message path.
- `UCX_CUDA_COPY_DMABUF=no` or `UCX_IB_GPU_DIRECT_RDMA=n` also avoid the error, by staging
  device memory through host memory. Results are correct; GPUDirect RDMA is not in use.
- Restricting QUDA's dslash policies (host-staged `0,1` or zero-copy-pack `10,11`) or setting
  `QUDA_ENABLE_GDR=0` avoided the failure in the tests too, by never handing a device send
  buffer to MPI. Those are ways around the transport, not fixes.

## Checking GDR on one node, without a batch job

Two ranks on one node can be forced through the HCA, so the transport path is exercised
inside an interactive session. Three things are needed:

- `UCX_TLS=rc_mlx5,ud_mlx5,cuda_copy,gdr_copy` and `UCX_NET_DEVICES=mlx5_0:1`. Keep `ud`
  in the list for connection set-up: with `rc_mlx5` alone, `ucx_perftest` reported no
  auxiliary transport and could not create the endpoint.
- `QUDA_ENABLE_P2P=0`, so QUDA hands the halo to MPI and allocates it as it does on a
  one-GPU node, and `QUDA_ENABLE_MPS=1`, so both ranks may share the node's one GH200.
- `mpirun --map-by :OVERSUBSCRIBE`: an interactive allocation of one task per node grants
  one slot, and `mpirun -np 2` otherwise refuses to start.

Run it outside an agent sandbox, which hides the GPU and HCA device files
([`../../conventions/agent-sandbox.md`](../../conventions/agent-sandbox.md)). Loopback on one
node proves the registration path, not inter-node behaviour; a multi-node run remains the
validation.
