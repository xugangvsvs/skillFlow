---
name: analyze-ims2
description: Use when analyzing IMS2 snapshots to inspect managed objects, state transitions, object state at a moment, fronthaul topology, or frame metadata in radio fault investigations.
inputs:
  - name: analysis_mode
    type: select
    label: Analysis Mode
    options:
      - topology
      - state
      - transitions
      - metadata
    default: topology
  - name: focus_object
    type: text
    label: Focus Object Regex
    placeholder: RMOD_L-\\d+$=stateInfo.operationalState
  - name: snapshot_file
    type: file
    label: IMS2 Snapshot File
    accept: .ims2
---

# Analyze IMS2

## Overview

Use `ims2_tool` to inspect IMS2 snapshots.

This is the canonical IMS2 skill used by fronthaul investigation workflows. Use it for managed-object state, state transitions, topology extraction, and snapshot metadata.

## When To Use

Use this skill when you need to:
- inspect managed objects in an IMS2 snapshot
- walk state transitions around a fault window
- query object state at a specific moment
- identify key attributes such as `l3Protocol`, `hwVariant`, or `serialNumber`
- run topology-oriented analysis with the `analyzer` subcommand
- inspect frame metadata with the `ims2` subcommand

Do not use this skill for SOAP, NETCONF, DFM, or binary tracing inputs.

## Preparation

Before running commands:

```bash
export PATH="${IMS2_BIN_DIR:-$HOME/bin}:$PATH"
command -v ims2_tool
```

If `ims2_tool` is missing, stop and tell the user. Install or update it via `../dev-skills/install.sh`.

## Quick Start

```bash
# 1. Walk transitions with JSON output
ims2_tool -i <FILE> --quiet-status walk -r '<REGEX>' -c --json <OUT.json>

# 2. Query state at a moment
ims2_tool -i <FILE> --quiet-status query -r '<REGEX>' -m last --json <OUT.json>

# 3. Topology summary
ims2_tool -i <FILE> --quiet-status analyzer
```

For `walk` and `query`, prefer JSON file output and parse that JSON instead of parsing stdout.

## Core Concepts

### Canonical Skill Contract

When this skill is invoked through a runner, use these canonical parameters:
- `ims2_path` - required input file
- `command` - `walk`, `query`, `analyzer`, or `ims2`
- `extra_args` - subcommand flags and values
- `quiet_status` - set to `true`
- `timeout_seconds`, `max_output_chars`, `max_lines` - only when needed

Prefer `ims2_path` over legacy aliases.

### JSON-First Rule

For `walk` and `query`:
- always prefer `--json <path>` in `extra_args`
- always set `quiet_status=true`
- parse the JSON file content returned by the tool
- do not rely on summary stdout for evidence extraction

### Choose The Right Subcommand

- `walk` for state transitions across time
- `query` for state at one moment
- `analyzer` for topology-oriented output
- `ims2` for frame metadata and lower-level inspection

### No-Match And Failure Behavior

`ims2_tool` may return empty results for a valid narrow query. Treat that as "no evidence found yet", not automatically as parser failure.

If output is truncated, narrow the query before increasing output caps.

## Regex Guidelines

Prefer tight, purpose-built regex:
- use `$` for exact object endings: `RMOD_L-\d+$`
- include the parameter when possible: `RMOD_L-\d+$=stateInfo.operationalState`
- anchor specific values when needed: `FAULT_NOTIF-1$=faultId=^10$`

Broad regex usually creates noisy JSON and weak evidence.

## Common Query Patterns

### Walk State Transitions

```bash
ims2_tool -i <FILE> --quiet-status walk -r 'RMOD_L-\d+$=stateInfo.operationalState' -c --json <OUT.json>
ims2_tool -i <FILE> --quiet-status walk -r 'FAULT_NOTIF-\d+$' -c --json <OUT.json>
```

### Query State At A Moment

```bash
ims2_tool -i <FILE> --quiet-status query -r 'CELL_M-\d+$=bandwidth' -m last --json <OUT.json>
ims2_tool -i <FILE> --quiet-status query -r 'RMOD_L-\d+$=stateInfo' -m '<TIMESTAMP>' --json <OUT.json>
```

### Restrict To A Time Window

```bash
ims2_tool -i <FILE> --quiet-status walk -r '<REGEX>' -n '<TIMESTAMP>=300' -c --json <OUT.json>
```

### Run Topology Analysis

```bash
ims2_tool -i <FILE> --quiet-status analyzer
```

## Output Shapes

For `query --json`, expect a state snapshot keyed by object.

For `walk --json`, expect objects plus a `changes` map keyed by object and timestamp.

Use `jq` for extraction, for example:

```bash
jq -r '.changes | keys[]' <OUT.json>
jq -r '.state | to_entries[] | "\(.key)\t\(.value.bldName)"' <OUT.json>
```

## Integration Contract

Use this skill in broader investigations when:
- `log_inventory.ims2_files` is non-empty, or
- managed-object state, state transitions, or protocol ownership must be established

Required outputs:
- selected IMS2 file and why it was chosen
- one focused JSON-backed `walk` or `query` result
- key attributes or state transitions relevant to the fault
- 1-3 evidence-backed findings with timestamps or object paths

Cross-check with:
- alarm history and DFM timing
- RP1 or NETCONF control-plane evidence
- topology or NR-cell tracing when needed

Do not:
- parse stdout summaries instead of JSON output for `walk` and `query`
- use broad regex when a tight object/parameter regex is possible
- increase output caps before narrowing the query

For topology and fault workflow details, use `TOPOLOGY_PLAYBOOK.md`.

## Common Mistakes

- forgetting `quiet_status=true`
- omitting `--json <path>` for `walk` or `query`
- using broad regex like `FAULT_NOTIF` instead of object-plus-parameter filters
- using `query` when the question really needs a transition history from `walk`
- treating an empty valid query as a tool failure

## Verify With Help

```bash
ims2_tool --help
ims2_tool walk --help
ims2_tool query --help
ims2_tool analyzer --help
ims2_tool ims2 --help
```
