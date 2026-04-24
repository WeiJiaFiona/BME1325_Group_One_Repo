# tests_week8

This directory is intentionally **not** included in the default `pytest.ini` testpaths yet.

Run explicitly:

```bash
cd /home/jiawei2022/BME1325/week8/merge
pytest -q tests_week8
```

Ablation (once substrate + hooks land):

```bash
MEMORY_ENABLED=0 pytest -q tests_week8
MEMORY_ENABLED=1 pytest -q tests_week8
```

Notes:
- Integration tests will SKIP until Developer A delivers `app_core/memory/*`.
- Prework tests validate env contract and fake services only.
