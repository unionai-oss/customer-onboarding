# Union v2 workshops — self-managed on GCP

A workshop series for teams running Union, covering Flyte v2 / Union 2.x
authoring patterns, integrations, and the operational judgment to use them well. Built to be
delivered live (90-minute sessions), but every notebook stands alone for self-paced use.

The sibling [`v1-onboarding/`](../v1-onboarding/) covers the v1 SDK; this series is
**v2-only** (`import flyte`) and assumes your platform is already deployed and running.

## 🗺️ Session map

| Session | Notebooks | You'll learn | Needs from platform team |
|---|---|---|---|
| **1** | [00-setup-and-verify](./00-setup-and-verify.ipynb) · [01-authoring-fundamentals](./01-authoring-fundamentals.ipynb) | Connect, run remotely from a notebook, TaskEnvironments, images → Artifact Registry, resources/GPUs | Project/domain, SSO, GAR repo |
| **2** | [02-parallelism-and-resilience](./02-parallelism-and-resilience.ipynb) · [03-caching-performance-reproducibility](./03-caching-performance-reproducibility.ipynb) | Fan-out/fan-in, retries/timeouts, OOM recovery, traces, signaling · cache behaviors, deterministic builds, spot/queues | Optional: spot node pool |
| **3** | [04-reusable-containers](./04-reusable-containers.ipynb) · [06-ray-on-union](./06-ray-on-union.ipynb) | Warm pools + micro-batching at scale · Ray integration extent, and **when Reusable Containers replace Ray** | **KubeRay operator + `ray` plugin enabled** |
| **4** | [07-apps-and-inference](./07-apps-and-inference.ipynb) | FastAPI/Streamlit/vLLM apps, autoscaling, cold-start economics, model wiring | Serving enabled; 1 GPU for vLLM |
| **5** | [08-v1-to-v2-migration](./08-v1-to-v2-migration.ipynb) + [appendices](./appendix/) | Concept map, a real pipeline ported, rollout strategy | — |
| **6** | [09-agents-and-sandboxing](./09-agents-and-sandboxing.ipynb) | Code sandbox for LLM-generated code, Monty workflow sandbox (programmatic tool calling / code mode), a ReAct agent from primitives | — (sandbox APIs are alpha; SDK pinned) |
| **7** *(optional)* | [05-gcp-data-and-integrations](./05-gcp-data-and-integrations.ipynb) | GCS File/Dir/DataFrames, secrets, BigQuery connector, remote tasks | BigQuery connector enabled |

Short on time? The must-have core is **00, 01, 02, 04, 06, 08**.

Give your platform team the **pre-workshop checklist** in
[appendix A](./appendix/A-platform-config-map.md) at least a week before sessions 3-4.

## 🛠️ Setup

1. **Python 3.12** — the kernel version must match the task images (all pinned to 3.12):

   ```bash
   python3.12 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Connect** — copy [`config-templates/config.yaml.example`](./config-templates/config.yaml.example)
   to `~/.flyte/config.yaml` and set your control-plane endpoint (ask your platform team), or:

   ```bash
   flyte create config --endpoint dns:///union.<your-company>.com
   ```

3. **Workshop settings** — `cp .env.example .env` and fill in project, domain, GAR registry,
   and bucket.

4. **Verify** — run [00-setup-and-verify](./00-setup-and-verify.ipynb) top to bottom:

   ```bash
   jupyter lab
   ```

## 📓 How notebooks run remotely (the four rules)

Tasks defined in notebook cells ship to the cluster as **pickled code bundles** — no files,
no git. The four rules that follow (taught in notebook 00):

1. Helpers used inside task bodies live in **notebook cells or installed packages** — never
   imported from local modules like `workshop_config.py` (client-side only).
2. Kernel Python **3.12** = task image Python 3.12.
3. `flyte.deploy()` (triggers, connectors, apps, named remote tasks) doesn't work from
   notebooks → those live in [`scripts/`](./scripts/) and are driven with `!python scripts/...` cells.
4. `Environment(include=...)` (extra-file bundling) also requires running from a file.

## 📁 Repo tour

```
v2-onboarding/
├── 00…09 *.ipynb            # the workshops (session map above)
├── workshop_config.py       # .env loader — CLIENT-SIDE ONLY (see rule 1)
├── config-templates/        # flyte CLI config template
├── scripts/                 # things that need deployment (rules 3-4)
│   ├── apps/                # FastAPI / Streamlit / vLLM app definitions (07)
│   ├── migration/           # v1 vs v2 side-by-side pipeline (08)
│   ├── triggers_deploy.py   # scheduled-task example
│   └── remote_task_deploy.py# shared task for the cross-team demo (05)
└── appendix/
    ├── A-platform-config-map.md      # platform-side config ↔ owner ↔ docs map + checklists
    └── B-observability-and-debugging.md
```

## 📌 Versions

Everything is exact-pinned for workshop reproducibility: **flyte 2.5.7** (SDK + plugins) —
see [requirements.txt](./requirements.txt). Task-image pins live inside each notebook's
`flyte.Image` definitions. To upgrade later: bump `flyte` and `flyteplugins-*` together,
re-run notebook 00, then the rest.
