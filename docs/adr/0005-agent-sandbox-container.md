# 5. The agent is a separate container, not a separate codebase

Date: 2026-08-22 · Status: Accepted

## Context

The brief asks for a containerized AI-agent sandbox with explicit, safe tools, and states
plainly: do not give the agent unrestricted system access. It also warns against
over-engineering and asks for a small number of clearly separated components.

Those pull in opposite directions. A genuine sandbox implies process isolation; a second
Python service implies a second dependency set, a second Dockerfile, and drift.

## Decision

Run the agent as a **second container from the same image**, with a different command:

- `api`   -> `uvicorn gridlab.web.app:app`   on the `frontnet` and `datanet` networks
- `agent` -> `uvicorn gridlab.agent.app:app` on `datanet` only, `read_only: true`, no volumes

The agent reaches the domain exclusively over HTTP to `http://api:8000`, with
`read_only: true`, `cap_drop: [ALL]`, `no-new-privileges`, a non-root user, and no volume
mounts.

**What this does and does not guarantee, stated precisely.** The container cannot read the
repository, cannot write anywhere except a tmpfs, cannot reach the `web` service, and holds
no database handle. The *model* has no shell tool, no file tool and no HTTP tool — it can
only act through the seven declared tools. What is **not** guaranteed is network egress:
the container must reach `api.anthropic.com`, and Docker cannot restrict egress by domain,
so outbound internet is open at the network layer. Closing that would require an egress
proxy, which is more machinery than this stage justifies. Do not describe the agent as
network-isolated; describe it as tool-constrained and filesystem-isolated, which is true.

Tools are the seven named in the brief, defined with `strict: true` JSON schemas and
`additionalProperties: false`. Zones are validated against the capability list; time ranges
are bounded; results are downsampled to a hard point cap before being returned to the model.

## Consequences

- A real isolation boundary for about ten lines of Compose, and one image to maintain.
- The agent cannot read a fixture directly or reach Electricity Maps directly, so every
  number it can see has passed through the domain layer and carries `provenance`.
- Because the agent talks HTTP, it can later be pointed at a deployed API, or replaced
  entirely, without touching the domain.
- The tool surface is a deliberate floor, not a ceiling. Adding a tool is a decision, and
  should get its own ADR if it can mutate anything.
