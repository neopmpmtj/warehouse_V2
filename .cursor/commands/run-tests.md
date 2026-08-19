---
name: run-tests
description: Run Django tests for CentCompras
---

Run the test suite:

1. `source .venv/bin/activate`
2. `python manage.py test --verbosity=2`
3. Summarize failures with app, file, and test name
4. Suggest minimal fixes without unrelated refactors
