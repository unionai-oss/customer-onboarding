# Appendix A · Platform configuration map

The workshops focus on authoring and integrations — the things you control from Python.
This appendix maps the **platform-side** items to where they are configured, who operates
them in a self-managed deployment, and what they unlock in the notebooks.

"Docs" paths refer to the Union documentation → **Deployment → Self-managed** section
(`deployment/selfmanaged/...` at [union.ai/docs](https://www.union.ai/docs/)).

| Capability | Where it's configured | Owner (self-managed) | Unlocks |
|---|---|---|---|
| **Dataplane install / upgrades / Helm rollouts** | `dataplane` Helm chart (`helm-chart-reference/dataplane`) | **Customer** performs rollouts; Union supplies charts, release notes, guidance | Everything |
| **GCS buckets + Workload Identity (GSA↔KSA)** | `selfmanaged-gcp/prepare-infra`: metadata + fast-registration buckets; `union-system` KSA (platform services) and `union` KSA (task pods) bound to GSAs | **Customer** (cloud IAM); Union reviews Union-side SA config | File/Dir/DataFrame I/O (05), fast registration, run metadata |
| **Image Builder → Artifact Registry** | `configuration/image-builder`: `imageBuilder.buildkit.enabled`, default repository, `google` credential helper; GAR repo needs `artifactregistry.writer` for the builder and `reader` for nodes | **Customer** (GAR + IAM); Union-side chart values with Union guidance | Every `flyte.Image` build (00 §5, 01 §3) |
| **Node pools & queues** | `configuration/node-pools` + GKE node pools (incl. spot pools, GPU pools with T4/L4/A100, taints/tolerations) | **Customer** (MIG vs non-MIG, spot vs on-demand, capacity reservations); Union provides sizing guidance | `flyte.GPU(...)` (01 §4), `queue=`/`interruptible` (03 §4) |
| **Compute plugins: Ray** | `configuration/plugins`: install KubeRay operator (`kuberay-operator` Helm chart + CRDs), add `ray` to `enabled_plugins`, configure log/dashboard links | **Customer** applies Helm changes; Union provides config | All of notebook 06 — **required before Session 3** |
| **Compute plugins: Spark / Dask / PyTorch** | Same `enabled_plugins` mechanism + per-plugin operator install | Customer applies; Union provides config | Future workshops on demand |
| **Connectors (BigQuery, …)** | Connector service enablement in dataplane values; custom connectors deploy as apps (`user-guide/build-apps/connector-app`) | Union-side config guidance; customer applies | BigQuery cells in 05 §4 |
| **Knative (apps/serving)** | `helm-chart-reference/knative-operator` | Customer applies; Union provides chart + guidance | All of notebook 07 |
| **Secrets** | `configuration/union-secrets` (K8s-backed; external secret stores integrable) | Union-side config; customer operates the store | `flyte.Secret` cells (05 §3), registry secrets (01) |
| **Authentication / SSO** | `configuration/authentication` (OIDC against your IdP; PKCE/DeviceFlow for CLI) | Union-side config guidance; customer owns IdP | `flyte.init_from_config()` login in every notebook |
| **Monitoring** | `configuration/monitoring`: built-in static Prometheus (task metrics, cost, GPU util — no setup); optional `kube-prometheus-stack` via `monitoring.enabled: true` for cluster health + Grafana | **Customer-hosted** Grafana; Union provides dashboard templates + guidance | Appendix B workflows |
| **Persistent task logs** | `configuration/persistent-logs`: FluentBit DaemonSet (on by default) under the `fluentbit-system` KSA writing to `persisted-logs/` in the dataplane bucket — the KSA's GSA needs bucket write access | Customer-operated logging stack; Union provides routing guidance | Log links in the UI outliving pods; `flyte get logs` |
| **Agent sandboxing** | SDK-level (`flyte.sandbox` — alpha): code sandbox builds ephemeral images via the Image Builder; Monty orchestrators only need `pydantic-monty` in the task image | No platform change beyond a working Image Builder | All of notebook 09 |
| **Multi-cluster / multi-region** | `configuration/multi-cluster` | Customer-operated; Union guidance | Future — GPU queues across regions |
| **Namespace mapping / RBAC** | `configuration/namespace-mapping`, `architecture/kubernetes-rbac` | Customer | The `<project>-<domain>` namespaces used throughout |
| **CVE patching (Union/Flyte software)** | Union release coordination; customer applies chart/image updates | **Union** provides patches + release notes; customer rolls out | — |
| **Cluster/OS/K8s ecosystem CVEs** (e.g. CoreDNS) | GKE + cluster tooling | **Customer**; Union advises on upgrade paths/compatibility | — |

## Pre-workshop checklist for the platform team

Before **Session 1** (notebooks 00-01):

- [ ] Workshop project + domain created; attendees have accounts (SSO) with access
- [ ] Artifact Registry repo reachable by the Image Builder (push) and nodes (pull)
- [ ] A GCS bucket task pods can read/write (for 05)

Before **Session 3** (notebooks 04 + 06):

- [ ] `unionai-reuse`-based reusable containers verified on a toy env (no platform change
      needed, but quota headroom for ~8 small pods helps)
- [ ] KubeRay operator installed and `ray` in `enabled_plugins` (06)
- [ ] Optional: a spot node pool for the `interruptible=True` demos (03)

Before **Session 4** (notebook 07):

- [ ] Knative/serving enabled in the dataplane
- [ ] One GPU (L4/T4-class) schedulable for the vLLM demo — or agree to skip it
- [ ] BigQuery connector enabled if running 05 in this session
