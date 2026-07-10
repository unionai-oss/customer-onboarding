# Union v2 baseline workshop — Review Radar

The **baseline** workshop series for customer engagements on Flyte v2 / Union 2.x. It is
deployment-agnostic (Serverless, BYOC, self-managed — any cloud) and built to be adapted
per customer: see [appendix A](./appendix/A-deployment-adaptation.md) for the prep sheet.

The series tells one story, **Review Radar**, from raw data to a production system:

```
raw reviews ─▶ durable datasets ─▶ parallel processing ─▶ cached features
                                                              │
      agents ◀─ live model API ◀─ trained model ◀─ warm-pool scoring
```

Every chapter advances the story with new platform capabilities, and every chapter also
stands alone for self-paced use. Built for live delivery in 90-minute sessions.

## 🗺️ Session map

| Session | Chapters | The story beat | Platform capabilities taught |
|---|---|---|---|
| **1** | [00-setup-and-verify](./00-setup-and-verify.ipynb) · [01-authoring-fundamentals](./01-authoring-fundamentals.ipynb) · [02-data-flow](./02-data-flow.ipynb) | Connect; generate the review corpus; land it as durable datasets | Notebook→remote execution, TaskEnvironments, images, resources, File/Dir/DataFrame, secrets, connectors |
| **2** | [03-processing-at-scale](./03-processing-at-scale.ipynb) · [04-caching-and-reproducibility](./04-caching-and-reproducibility.ipynb) | Enrich every review in parallel; make iteration cheap and releases reproducible | Fan-out/fan-in, retries/timeouts, OOM recovery, traces, signaling · cache behaviors, deterministic builds, spot/queues |
| **3** | [05-reusable-containers](./05-reusable-containers.ipynb) · [06-training-at-scale](./06-training-at-scale.ipynb) | Score the whole corpus on warm pods; train the sentiment model + HPO | ReusePolicy + micro-batching · training artifacts, sweep on Union primitives vs **Ray**, decision framework |
| **4** | [07-serving](./07-serving.ipynb) · [08-agents-and-sandboxing](./08-agents-and-sandboxing.ipynb) | The model goes live; an agent triages reviews on top of it | Apps + train→serve `RunOutput` wiring, autoscaling, vLLM · code sandbox, code mode (Monty), agent loop from primitives |
| **5** *(for v1 estates)* | [09-migration-v1-to-v2](./09-migration-v1-to-v2.ipynb) + [appendices](./appendix/) | Bring the existing estate along | Concept map, ported pipeline, rollout strategy |

Short on time? The story core is **00 → 07** in order; 08 and 09 detach cleanly.

Give the platform team the **capability checklist** in
[appendix A](./appendix/A-deployment-adaptation.md) at least a week before sessions 3-4.

## 🛠️ Setup

1. **Python 3.12** — the kernel version must match the task images (all pinned to 3.12):

   ```bash
   uv venv --python 3.12 && source .venv/bin/activate
   uv pip install -r requirements.txt
   ```

2. **Connect** — copy [`config-templates/config.yaml.example`](./config-templates/config.yaml.example)
   to `~/.flyte/config.yaml` and set the engagement's endpoint, or:

   ```bash
   flyte create config --endpoint dns:///<union-endpoint>
   ```

3. **Workshop settings** — `cp .env.example .env` and fill in per
   [appendix A §2](./appendix/A-deployment-adaptation.md).

4. **Verify** — run [00-setup-and-verify](./00-setup-and-verify.ipynb) top to bottom.

## 📓 How notebooks run remotely (the four rules)

Tasks defined in notebook cells ship to the cluster as **pickled code bundles** — no
files, no git. The four rules that follow (taught in notebook 00):

1. Helpers used inside task bodies live in **notebook cells or installed packages** —
   never imported from local modules like `workshop_config.py` (client-side only).
2. Kernel Python **3.12** = task image Python 3.12.
3. `flyte.deploy()` (triggers, connectors, apps, named remote tasks) doesn't work from
   notebooks → those live in [`scripts/`](./scripts/), driven with `!python scripts/...` cells.
4. `Environment(include=...)` (extra-file bundling) also requires running from a file.

## 📁 Repo structure

```
v2-baseline/
├── 00…09 *.ipynb            # the chapters (session map above)
├── workshop_config.py       # .env loader — CLIENT-SIDE ONLY (rule 1)
├── config-templates/        # flyte CLI config template
├── scripts/                 # things that need deployment (rules 3-4)
│   ├── apps/                # Review Radar API (+ Streamlit, vLLM) for 07
│   ├── migration/           # v1 vs v2 side-by-side pipeline for 09
│   ├── triggers_deploy.py   # nightly-ingest schedule example
│   └── remote_task_deploy.py# shared task for the cross-team demo (02)
├── appendix/
│   ├── A-deployment-adaptation.md    # per-customer prep: fill-ins, checklists, ownership matrix
│   └── B-observability-and-debugging.md
└── self-managed-setup/      # example of per-engagement additions (here: Helm values
                             # from a self-managed GCP engagement) — see "Adapting" below
```

## 🔁 Adapting per customer

This folder is the baseline — copy it (or branch) per engagement and:

1. Fill in `.env` + `config.yaml` ([appendix A §2](./appendix/A-deployment-adaptation.md))
2. Walk the platform team through the capability checklist (appendix A §3)
3. Swap the story's ingest and the warehouse cell for the customer's real sources
   (appendix A §5), and set GPU device names to what their deployment schedules
4. Keep customer-specific material in added appendices so improvements to the chapters
   can merge back into the baseline

## 📌 Versions

Everything is exact-pinned for workshop reproducibility: **flyte 2.5.7** (SDK + plugins) —
see [requirements.txt](./requirements.txt). Task-image pins live inside each notebook's
`flyte.Image` definitions. To upgrade: bump `flyte` and `flyteplugins-*` together,
re-run notebook 00, then the rest.
