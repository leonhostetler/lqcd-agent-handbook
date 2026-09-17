---
title: Rank placement and which halo faces cross the fabric
summary: QUDA selects its peer-to-peer halo path per direction by comparing neighbour hostnames, so the rank-to-node mapping decides which faces cost fabric bandwidth — and off-node halo per unit local volume, not total halo, is what orders decompositions.
scope: [software:quda]
load_when: Choosing a rank grid or rank ordering, comparing decompositions of equal volume, or explaining why two decompositions with identical total halo differ in speed.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/include/communicator_quda.h
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/include/comm_quda.h
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/lib/communicator_stack.cpp
  - operator's screened decomposition records
observed: "2026-09-17"
observed_on:
  software:
    quda:
      commit: f2df42ac4caa0cd51b96b01006a1c25c8d753425
      branch: develop
---

# Rank placement and which halo faces cross the fabric

Two decompositions of the same lattice onto the same number of ranks can have **identical total
halo area** and still differ in speed, because total halo does not distinguish a face exchanged
over the intra-node link from one exchanged over the fabric. Which is which is set by the
rank-to-node mapping, not by the rank grid alone.

## QUDA decides the path per direction, by hostname

`comm_peer2peer_enabled(dir, dim)` is a per-direction, per-dimension flag. It is set during
communicator initialisation, and the test is a hostname comparison against the neighbour rank
followed by a device-accessibility check:

```cpp
// if the neighbors are on the same [host]
if (!strncmp(hostname, &hostname_recv_buf[QUDA_MAX_HOSTNAME_STRING * neighbor_rank], ...)) {
  bool can_access_peer = comm_peer2peer_possible(gpuid, neighbor_gpuid);
  int access_rank = comm_peer2peer_performance(gpuid, neighbor_gpuid);
  if ((can_access_peer && access_rank <= enable_p2p_max_access_rank) || gpuid == neighbor_gpuid) {
    peer2peer_enabled[dir][dim] = true;
```

So each of a rank's eight neighbours is independently on the peer-to-peer path or the fabric path,
and the decision is a property of **where that neighbour's rank was placed**.

**Sharing a node is necessary and not sufficient.** The accessibility check can still fail, the
access rank must be within `enable_p2p_max_access_rank`, and the whole mechanism is off when
`enable_p2p` is false. There is also an explicit guard that suppresses one direction of a
bidirectional pair when a dimension holds exactly two ranks. Do not infer the path from the
placement alone when it matters — the correctness consequences of the two paths differ, and
[`../development.md`](../development.md) owns that hazard.

## The geometry that follows

Let a node hold some number of consecutive ranks in each direction. Then, per direction:

- a direction in which a node holds **one** rank sends **both** its faces over the fabric;
- a direction in which a node holds **more than one** rank keeps the interior exchanges on-node and
  sends only the two boundary faces off-node; and
- a direction in which **every** rank of the communicator lives on one node sends **neither** face
  off-node, because the periodic wrap lands on the same node. This is the case QUDA's
  two-rank guard above is about.

**The consequence is that the rank ordering is a performance parameter, not bookkeeping.** Holding
the rank grid fixed and changing which ranks are co-located changes the off-node face set, and
therefore changes fabric traffic, with no change to total halo, local volume, or any quantity a
decomposition check reports.

## Order candidates by off-node halo per unit local volume

The comparable figure is off-node halo area divided by local volume:

- **off-node rather than total**, because the intra-node link and the fabric are not the same
  resource — see the node type's `accelerator.interconnect` and `network` fields in the machine
  profile for what each one is on a given system; and
- **per unit volume**, because per-rank compute per iteration scales with local volume times batch
  width, so dividing by volume makes the figure independent of batch width and comparable across
  candidates that batch differently.

**Enumerate the legal decompositions rather than hand-picking a family.** In one recorded case a
document's hand-picked candidates all shared a single shape, never split two of the four
directions, and never said why; enumerating the legal space turned up candidates at a different
partition count that beat the campaign's fastest on this metric and had never been run. The
constraint set is arithmetic — each factor must divide the corresponding communicator extent, and
the quotient must be divisible by the node's rank extent in that direction, or one node's devices
land in different partitions.

## What this metric is worth, stated precisely

**Treat it as a good ordering statistic with a known failure, not as a predictor.** `[experiment]`
Its evidence base is one pair that cleanly separates it from total halo — identical total halo,
different off-node halo, and the lower-off-node candidate won — plus a second pair where both
metrics agreed and it was right. Against that, one pair the metric scored as an exact tie measured
several percent apart, which is a genuine miss.

The likely cause of the miss is the part the metric does not carry: **message size and
reduction latency**. The tied pair differed by a factor of two in largest face area, and a
per-message or per-collective term is invisible to an area-per-volume figure. So the metric orders
candidates that differ in *where* their traffic goes, and says nothing about candidates that
differ mainly in *how it is packaged*.

Three further limits:

- **A traffic reduction is not a speedup.** In the single calibration point available, roughly half
  of the off-node traffic reduction reached wall time; the conversion depends on the
  fabric-to-intra-node cost ratio, which this leaf does not measure.
- **Message count is unmodelled**, and it is where the remaining disagreement lives.
- **The effect on device memory is unmodelled.** A peer-to-peer neighbour's ghost buffer is mapped
  rather than allocated locally, so changing which neighbours are co-located moves the high-water
  mark by an amount [`../solvers/staggered-memory.md`](../solvers/staggered-memory.md) does not
  carry. At a tight margin, re-measure rather than assuming the change is memory-neutral.

Finally, a warm tunecache does **not** distinguish two placements of the same rank grid; see
[`autotuning.md`](autotuning.md), which owns that trap and the remedy. An A/B across a placement
change on a shared cache is biased, not merely noisy.
