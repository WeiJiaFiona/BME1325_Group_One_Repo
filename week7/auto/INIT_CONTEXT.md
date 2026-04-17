# Week7 Auto Init Context

Use `week7_auto` as the only active project root for Week 7 work.

## Working Rule

- Run, test, and edit only inside `week7_auto`.
- Do not import code, templates, storage, or runtime data from external source directories.
- If a required file is missing, copy it into `week7_auto`; do not point back to the original source tree.

## Baseline Source

The baseline in `week7_auto` is a local copy built from:

- primary baseline source: `EDSim-threejs`
- missing runtime directories copied from `EDSim-main`:
  - `environment/frontend_server/storage/`
  - `environment/frontend_server/temp_storage/`

This means:

- `analysis/`, `reverie/`, `environment/frontend_server/`, `environment/react_frontend/`, `tests/`, and the root scripts in `week7_auto` are now local copies
- `storage/` and `temp_storage/` under `week7_auto/environment/frontend_server/` are also local copies

## Week 6 Overlay

The Week 6 integration layer copied into `week7_auto` consists of:

- `week5_system/`
- `environment/frontend_server/frontend_server/urls.py`
- `environment/frontend_server/translator/views.py`
- `environment/frontend_server/templates/landing/landing.html`
- `environment/frontend_server/templates/home/start_simulation.html`
- `environment/frontend_server/templates/home/home.html`

These files provide:

- `ui_mode=auto|user`
- `/mode/user/*` routes
- `/ed/handoff/*` routes
- `/ed/queue/snapshot`
- user-mode chat and handoff integration through `week5_system.app.api_v1`

## Canonical Runtime Paths

Treat these as the only canonical runtime paths:

- frontend root:
  `week7_auto/environment/frontend_server/`
- storage root:
  `week7_auto/environment/frontend_server/storage/`
- temp storage root:
  `week7_auto/environment/frontend_server/temp_storage/`
- backend root:
  `week7_auto/reverie/backend_server/`

## Current Status

- Baseline files have been copied into `week7_auto`.
- `storage/` and `temp_storage/` have been copied into `week7_auto`.
- Week 6 overlay files and `week5_system/` have been copied into `week7_auto`.
- Further Week 7 feature work must continue on this local copy only.
