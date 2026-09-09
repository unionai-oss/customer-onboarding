"""Fork demo for 05-resilience-and-recovery §6.

Lives in a .py file, NOT a notebook cell, and that is the whole point: notebook tasks
ship as pickled bundles that version on the bundle itself, so any edit renames every
action and fork reuses nothing. Fork needs file-based tasks (authoring rules 3-4).

The story: stage 1 is slow and succeeds, stage 2 has a bug and fails. Re-running from
scratch would repeat the slow stage. Forking replays it and re-executes only the fix.

    # 1. Run it. `enrich_batch` succeeds (slowly); `score_batch` raises.
    python scripts/fork_demo/pipeline.py

    # 2. Fix the bug: set BUG = False below.

    # 3. Fork the failed run with your fixed code.
    flyte fork <run-name> scripts/fork_demo/pipeline.py main

Watch the run in the UI: the four `enrich_batch` actions show as RECOVERED (reused, never
re-executed), and only `score_batch` runs. Compare with a plain rerun, which repeats
everything:

    flyte rerun <run-name>

Requires flyte 2.6.x + flyteplugins-union (both pinned in pyproject.toml). Remote-only.
"""

import asyncio
from typing import List

import flyte

# ── The bug. Flip to False in step 2, then fork. ─────────────────────────────────
# NOTE: this is a module-level constant, so editing it does NOT rename any action.
# It only matters because `score_batch` reads it in its own body — and that body is
# what fails. If a task that *succeeded* read this constant, fork would silently reuse
# it and your edit would have no effect (05 §6). That is the trap, in miniature.
BUG = True

env = flyte.TaskEnvironment(
    name="fork_demo",
    image=flyte.Image.from_debian_base(name="fork-demo", python_version=(3, 12)),
    resources=flyte.Resources(cpu="1", memory="1Gi"),
)


@env.task
async def enrich_batch(batch: List[int]) -> List[int]:
    """Stage 1: slow and correct. This is the work you do not want to repeat."""
    await asyncio.sleep(20)  # stand in for real per-batch work
    return [n * 2 for n in batch]


@env.task
async def score_batch(values: List[int]) -> float:
    """Stage 2: buggy. Divides by zero on the first pass."""
    divisor = 0 if BUG else len(values)
    return sum(values) / divisor


@env.task
async def main(n_batches: int = 4, batch_size: int = 5) -> float:
    batches = [list(range(i * batch_size, (i + 1) * batch_size)) for i in range(n_batches)]

    # Four child actions, each slow, each of which will be reused on fork.
    enriched: List[List[int]] = list(
        await asyncio.gather(*(enrich_batch(batch=b) for b in batches))
    )
    flat = [n for sub in enriched for n in sub]

    # The action that fails, and the only one that should re-execute after the fix.
    return await score_batch(values=flat)


if __name__ == "__main__":
    flyte.init_from_config()
    run = flyte.run(main)
    print(run.url)
    run.wait()
    print(f"\nRun name: {run.name}")
    print("Now set BUG = False above, then:")
    print(f"    flyte fork {run.name} scripts/fork_demo/pipeline.py main")
