# Week 9 ED-HIS Contract Freeze v1

This document is the Week 9 local source of truth for the Developer A minimum substrate gate.

## Working root

All Week 9 HIS implementation work must happen under:

`/home/jiawei2022/BME1325/week9/week9_v1`

Any older document that mentions `week8/merge` is outdated for implementation purposes.

## Frozen identifiers

- `patient_id = P-{8 hex}`
- `encounter_id = E-{14 timestamp}-{4 hex}`

## External triage representation

All HIS-facing or cross-developer triage values must normalize to:

- `ctas_level`: `L1`, `L2`, `L3`, `L4`, `L5`
- `zone`: `red`, `orange`, `yellow`, `green`, `blue`

## Frozen route names

- `transfer`
- `admissions`
- `summary`
- `timeline`

## HIS event envelope

Every normalized HIS event must provide:

- `event_id`
- `event_type`
- `occurred_at`
- `patient_id`
- `encounter_id`
- `source`
- `payload`

## Memory to HIS input expectations

The HIS substrate expects these existing Memory v1 inputs:

- `app_core.memory.schema.MemoryItem`
- `app_core.memory.schema.CurrentEncounterSummary`
- `app_core.memory.schema.HandoffMemorySnapshot`

## Freeze rule

After Developer B starts integration, file names, public service method names, table names, and config variable names must not be renamed without compatibility aliases.
