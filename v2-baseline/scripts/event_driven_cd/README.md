# Event-driven CD: controlling which version production runs

An external system — a Lambda, EventBridge, a webhook relay — fires a pipeline when
something happens. Two requirements pull against each other:

1. The caller must **not know a version**. It fires by name; its code never changes.
2. You must **keep control** over which version it reaches, and be able to change
   that — including backwards — without touching the caller.

In Flyte 1 this was launch-plan activation: `fetch_active_launchplan()` resolved the
name, and `update_launch_plan(..., ACTIVE)` chose the version.

## The Flyte 2 answer: a version label

Flyte 2 has no active/default version — a task is always addressed by an exact
version. But **task versions are mutable**: re-deploying an existing version swaps
its code in place. That is enough.

Deploy each release twice — once under an immutable tag that is a permanent record,
once under a label meaning "what production runs now":

```
version "r1"    <- immutable; never overwritten
version "r2"    <- immutable; never overwritten
version "prod"  <- overwritten each release; the caller pins this
```

The caller pins the label, forever:

```python
task = flyte.remote.Task.get("event_driven.ingest", version="prod")
run  = flyte.run(task, object_key=..., event_time=...)
```

Both requirements are met using only `flyte deploy`.

### Walkthrough

Run from the `v2-baseline` root. Tags are `r1`/`r2` rather than `v1`/`v2`, which in
this repo read as *Flyte* v1/v2.

```bash
# 1. Release r1
flyte deploy --version r1   scripts/event_driven_cd/pipeline.py env
flyte deploy --version prod scripts/event_driven_cd/pipeline.py env

# 2. Fire it the way the Lambda will — names a label, never a version
python scripts/event_driven_cd/invoke.py --object-key s3://bucket/a.nc

# 3. Release r2. Production follows; the caller is untouched.
flyte deploy --version r2   scripts/event_driven_cd/pipeline.py env
flyte deploy --version prod scripts/event_driven_cd/pipeline.py env

# 4. Roll back: check out the older commit, re-publish under the label
flyte deploy --version prod scripts/event_driven_cd/pipeline.py env
```

### Which code is a release running?

Runs launched through the label record their version as `prod`, so read the **code
bundle** instead. It is content-hashed, so matching it against your immutable tags
identifies the release exactly:

```python
def bundle(version):
    args = list(remote.Task.get("event_driven.ingest", version=version).fetch()
                .pb2.spec.task_template.container.args)
    return args[args.index("--tgz") + 1].rsplit("/", 1)[-1]

bundle("r2") == bundle("prod")   # True -> prod is running r2's code
```

Every run stores this too, so past runs remain traceable to exact code. `invoke.py`
prints it before launching. Don't keep a release marker in your source to track
this — it is duplicated state that silently drifts.

### `--copy-style none`

The label deploy re-uploads a bundle identical to the one the tag deploy just sent.
If your images have code baked in, add `--copy-style none` to make it a
metadata-only write.

Not baking is the default, though: Flyte 2 ships code as a bundle to blob storage
and the pod pulls it at runtime, so the image carries only the interpreter and
dependencies. Code is in the image only via `Image.with_source_folder()`,
`.with_uv_project()`, a Dockerfile `COPY`, or similar. The images here are
dependencies-only, so `--copy-style none` would register a label with no code to run.

### Why not `auto_version="latest"`

`Task.get(name, auto_version="latest")` resolves to the most recently deployed
version, so newest deploy always wins. The caller stays version-ignorant, but you
lose control: nothing to pin, and the only way off a bad version is deploying
another. Good in development, wrong here.

## When to use a trigger instead

A trigger is a named pointer that stores which version it designates, so you move it
without redeploying (`pointer_pipeline.py`, `repoint.py`, `invoke.py --mode pointer`):

```bash
flyte deploy --version r1 scripts/event_driven_cd/pointer_pipeline.py env
python scripts/event_driven_cd/repoint.py prod event_driven_pointer.ingest --to r1
```

Two things it gives you that the label does not:

- **Rollback without rebuilding.** One write, so it still works when old code no
  longer builds — and it cannot overwrite the tag you are rolling back to. With a
  label, rolling back means redeploying from an old commit; if your working tree
  isn't exactly that commit, you overwrite the record you were restoring.
- **Release history.** Every move is a recorded revision with an author, rather than
  only "who deployed last".

The costs: no CLI or console support for moving a pointer, so `repoint.py` is a
script; and a trigger currently requires a schedule, so the pointer declares an inert
cron and is deployed inactive.

Both approaches share one property worth planning around: **deploying publishes**.
There is no inert "registered but not yet exposed" state — a deploy reaches
name-only callers immediately, and re-points a task's triggers. If you need a staging
gate, deploy to a non-production domain first.

## Choosing

| | caller version-ignorant | you control the version | rollback | release history |
|---|---|---|---|---|
| `auto_version="latest"` | yes | **no** | redeploy | version list |
| **version label** | yes | yes | rebuild + redeploy | last deploy only |
| trigger pointer | yes | yes | one write, no rebuild | full revisions |

Start with the label. Move to the trigger if rollback speed or release history
justifies the extra tooling.
