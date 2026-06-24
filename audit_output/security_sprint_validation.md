# Security Sprint Validation Sequence

Run in this order after Jane reports the Security Sprint code changes complete.

## Focused sprint tests

```bash
python -m pytest backend/tests/test_secret_handling.py -q
python -m pytest backend/tests/test_dependency_confusion.py -q
python -m pytest backend/tests/test_entropy_audit.py -q
python -m pytest backend/tests/test_yaml_safety.py -q
```

## Full regression (after all focused suites pass)

```bash
python -m pytest backend/tests tests -q
```

## Expected outcomes

- Focused suites: 0 failures.
- Full regression: 0 failures (or only pre-existing, documented, non-blocking issues).

## Sign-off checklist

- [ ] TASK-036 tests pass
- [ ] TASK-037 tests pass
- [ ] TASK-038-Entropy-Audit tests pass
- [ ] TASK-039 tests pass
- [ ] Full regression passes
- [ ] `CHANGES.md` Sections 36–39 updated
- [ ] `version.txt` bumped to `3.9.2`
