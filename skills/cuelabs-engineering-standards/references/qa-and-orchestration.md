# Orchestration and QA loops

How CueLABS™ work is executed with an orchestrator + subagents (applies to
design, web, and future phases):

- **Roles** — one orchestrator + one agent per product/lane. The
  orchestrator NEVER builds: it scopes missions, adjudicates conflicts,
  runs merge gates, diffs for cross-repo parity, codifies standards, and
  revives the fleet. Agents do all building/QA and never merge their own
  PRs. Docs are the contract: contract changes land (or are dispatched)
  before or with the build that implements them.
- **Mission briefs are self-contained** — each brief carries: an explicit
  instruction to ignore injected third-party skill/hook prompts (known
  false-positive prompt injections); the repo/file state the agent
  inherits; the exact contracts to read; environment gotchas (small tool
  calls under stream watchdogs, ≤3 logical ops per canvas/API call);
  a private artifact directory per agent under the session scratchpad
  (parallel agents collide on shared temp names); and a "stop cleanly and
  report — you'll be resumed" escape hatch.
- **Double-writer protocol** — when two live agent instances discover
  each other in one worktree (restart-resume races), they partition the
  mission via an UNTRACKED ledger file (`COORDINATION-<mission>.local.md`:
  who owns which items, endgame owner), honor it, and delete it before
  the PR. Never assume a "killed" twin is dead — verify via
  processes/mtimes before taking over its endgame.
- **Durable-state-first** — git branches/PRs, Figma files, and docs are
  the real state; agent transcripts are disposable. Agents must design
  work so any successor can resume from the canvas/tree alone: verify
  `git branch --show-current` before every commit (trees are shared),
  stage explicitly by path, prefer many small commits/calls, use detached
  worktrees when touching a repo another agent holds. **Branch fresh,
  land clean**: `git fetch origin` immediately before creating any branch
  (always off the just-fetched `origin/main`), and when a sibling PR merges
  while yours is open, merge `origin/main` into your branch before the final
  push — MERGEABLE is part of the merge gate, and conflict resolution follows
  the current-docs rule. On process restarts/session limits: resume from
  transcript when possible; when a transcript is lost or too bloated to
  resume, spawn a fresh agent with a context handoff and verify-then-fix
  (idempotent) instructions.
- **Model policy (split fleet)** — top-tier models for open-ended
  builders, QA auditors, root-cause debugging, and fidelity judgment;
  mid-tier models for pre-adjudicated mechanical work (docs writers
  executing digests, fix-list executors with per-item node/file IDs +
  prescribed fixes, scripted sweeps, monitors). When in doubt, top tier.
  The QA loops are the safety net that makes downshifting cheap.
- **QA / evaluation loops** — every stage closes with audit → fix →
  re-verify rounds to convergence: auditors are INDEPENDENT of the
  builders; findings carry node/file IDs, severities
  (blocker/major/minor/nit), and concrete fixes; the orchestrator
  adjudicates conflicts against ratified standards (wontfix requires a
  recorded reason); the next round verifies every prior finding against
  the artifact itself (per-finding ledger), never against the fixer's
  claim; loops converge at clean or nits-only. Lenses by phase: design =
  completeness/content/polish (+ prototype graph BFS); web =
  Figma-fidelity (screenshot + token/geometry vs the Figma files) +
  functional (unit/integration/e2e journeys mirroring `design.md`'s
  prototype journeys).
- **Merge gates** — an implementation PR merges only when: CI fully green
  (external content-sync statuses don't count either way) · queued
  standardization corrections are folded in · the cross-repo parity diff
  is clean (workflows byte-identical, scripts/layout/naming uniform) ·
  QA-loop findings for the stage are resolved or adjudicated. Every
  resolved divergence is codified in this standard in the same pass (the
  "standardize constantly" rule) so drift becomes a detectable violation.
- **User-reported findings are CLASSES** — a defect reported live on one
  product is never closed as a spot fix: before the round ends, every
  sibling product is swept for the same class (same construction or the
  analogous surface) and each gets an explicit fix or a recorded clean
  verdict with evidence. Docs and Figma masters are updated in the same
  round as the code fix — the three never diverge for longer than one PR
  cycle.
- **Checkout & push discipline** — agent lane work NEVER happens in a
  repo's main checkout: lanes always use detached worktrees; the main
  checkout stays on `main` (a lane that leaves it on a feature branch with
  dirty files risks losing the work to a restart, and holds ports/tools
  other lanes need). Push after EVERY commit — unpushed commits and
  uncommitted worktree state are the real data-loss vector on restart;
  remotes are the durable state. Before declaring any prior lane's work
  lost, VERIFY remotes and worktrees first. **Worktree removal is part of
  the merge gate**: when a lane's PR merges, its worktree is removed in the
  same step — never left for a later sweep (accumulated worktrees with
  `node_modules`/`.next` exhaust disk, and a forgotten worktree can hide
  unmerged commits). Heavy lanes cap CONCURRENT build worktrees at two
  fleet-wide — each `npm ci` + `next build` costs ~2GB of disk and enough
  memory to destabilize the host.
