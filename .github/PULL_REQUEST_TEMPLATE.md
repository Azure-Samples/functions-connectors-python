## Summary

<!-- What changed and why. Link related issues, for example: Fixes #123. -->

## Affected samples

<!-- Sample paths and delivery modes (polling/webhook), or "repo-wide". -->

## Validation

<!-- Commands run and results, for example `python -m py_compile`, `ruff check`, and `pip-audit`.
Manual trigger testing: state local or Azure and the result, or "not run". Use test data only. -->

## Checklist

- [ ] Validation passed, or I explained above why it does not apply.
- [ ] Each polling/webhook sample still restores, builds, and deploys independently.
- [ ] Updated affected READMEs and the `Unreleased` section of CHANGELOG.md.
- [ ] Kept existing Learn metadata (`urlFragment`) stable in sample READMEs.
- [ ] Included no credentials, `local.settings.json`, `.azure` environments, build output, real payloads, or unredacted logs/screenshots.
