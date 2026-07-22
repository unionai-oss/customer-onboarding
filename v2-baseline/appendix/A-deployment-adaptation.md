# Appendix A · Adapting this workshop to a customer deployment

The notebooks are **deployment-agnostic**: the same code runs on Union BYOC and
self-managed, on any cloud. What changes per engagement is (a) a handful of values in
`.env` / `config.yaml`, and (b) which platform capabilities need to be confirmed or
enabled before certain chapters. This appendix is the prep sheet.

## 1. Who operates what

| Capability | BYOC | Self-managed |
|---|---|---|
| Control plane | Union | Customer (Union-supplied charts) |
| Data plane / clusters | Customer account, Union-managed | Customer |
| Image builder + registry | Union-managed (customer registry possible) | Customer registry (ECR / Artifact Registry / ACR) |
| Object store | Customer bucket | Customer bucket |
| GPU / spot capacity | Customer node pools | Customer node pools |
| Queues (scheduling lanes: global concurrency cap, depth, priority) | Customer defines via CLI/UI, Union guides | Customer defines via CLI/UI, Union guides |
| Plugins (Ray, Spark, connectors) | Union enables | Customer applies Helm config, Union guides |
| Serving (apps) | Union enables | Customer applies Helm config, Union guides |
| SSO / identity | Customer IdP | Customer IdP |
| Cluster access (`kubectl`) | Customer | Customer |

Sections of the notebooks marked *"Under the hood"* assume data-plane access (`kubectl`),
which both models provide.

## 2. Per-engagement fill-ins

Collect these during prep and put them in `.env` + `config-templates/config.yaml.example`:

| Value | Where | Notes |
|---|---|---|
| Control-plane endpoint | `config.yaml` `admin.endpoint` | `dns:///...` |
| Org / project / domain | `config.yaml` `task.*`, `.env` | Create a dedicated workshop project |
| `IMAGE_REGISTRY` | `.env` | Empty where Union-managed. AWS: `<acct>.dkr.ecr.<region>.amazonaws.com/<repo>` · GCP: `<region>-docker.pkg.dev/<proj>/<repo>` · Azure: `<registry>.azurecr.io/<repo>` |
| `OBJECT_STORE_URI` | `.env` | With scheme: `s3://` / `gs://` / `abfs://`, used by the `from_existing_remote` cells in 02 |
| Warehouse (optional) | `.env` | 02 §4 ships a BigQuery example; swap the cell for Snowflake/Databricks to match the customer |
| GPU device names | notebook cells | `flyte.GPU(device=...)` in 01/06/07, set to what the deployment schedules (T4/L4/A100/H100/...) |
| HF model (optional) | `.env` | vLLM add-on in 07 |

## 3. Capability checklist by session

Before **Session 1** (00-02):

- [ ] Workshop project + domain created; attendees have accounts (SSO) with access
- [ ] Image build path verified once (notebook 00 §5 does this; on customer registries,
      confirm the builder has push and the nodes have pull access)
- [ ] An object-store path task pods can read/write (for 02); one small sample file
      placed at `OBJECT_STORE_URI` for the `from_existing_remote` demo
- [ ] Optional: warehouse connector enabled + a readable table (02 §4)

Before **Session 2** (03-04):

- [ ] Optional: spot/preemptible capacity for the `interruptible=True` demo (04 §4)
- [ ] A named queue with a concurrency cap, to demo cluster-wide bounding (03 §2) and
      `queue=` targeting (04 §4), e.g. a `moderation-api` queue capped at ~20 concurrent actions

Before **Session 3** (05-06):

- [ ] Reusable containers verified on a toy env (no platform change needed; quota
      headroom for ~8 small pods helps)
- [ ] **Ray plugin enabled** for 06 §3 (KubeRay operator + plugin enablement: on
      self-managed this is the customer's Helm change; on BYOC ask Union).
      06 §§1-2 need nothing special, so the session still works if this slips.

Before **Session 4** (07-08):

- [ ] Serving/apps enabled in the deployment
- [ ] One small GPU schedulable for the vLLM add-on, or agree to skip 07 §3
- [ ] `flyte.sandbox` chapters (08) need only a working image builder; note the API is
      **alpha**. Re-verify on the pinned SDK before the session

## 4. Deployment-specific doc entry points

Point the customer's platform team at the matching deployment guide in the Union docs
(Deployment section): **BYOC** (per-cloud data-plane setup) or **Self-managed** (per-cloud
install: AWS / GCP / Azure / OCI / CoreWeave / Nebius / generic, plus configuration pages
for image-builder, plugins, node-pools, secrets, authentication, monitoring, persistent
logs, multi-cluster).

This appendix records *ownership and readiness*: who sets a thing up and whether it's done
for a given engagement. It is **not** a how-to. For the actual configuration steps, use the
docs above, plus these the notebooks link to directly:

- **Queues** (create a queue, set its concurrency cap / depth / priority):
  <https://www.union.ai/docs/v2/union/user-guide/task-configuration/queues/>
- **Ray plugin enablement** (self-managed): the *plugins* configuration page in the
  Self-managed deployment guide.

## 5. Extending the baseline per customer

- **Swap the story's ingest** (01/02) for the customer's real source (an API, a bucket
  listing, a warehouse query), keeping task names so later chapters still read.
- **Swap the warehouse cell** (02 §4) to the customer's connector.
- **Re-scope 06 §3**: if the customer has no Ray history, demo it briefly and spend the
  time on the decision framework; if they're Ray-heavy, extend with their real workload.
- **Add customer-specific appendices** rather than editing chapters, which keeps the baseline
  mergeable back.
