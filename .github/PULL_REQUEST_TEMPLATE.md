<!-- Thanks for contributing to acroforge! Please fill this out. -->

## What does this PR do?

<!-- One or two sentences. Link any related issue: "Fixes #123". -->

## Checklist

- [ ] Tests pass locally - `uv run pytest`
- [ ] Lint + types clean - `uv run ruff check src tests` and `uv run mypy src`
- [ ] **No new copyleft deps** - `uv run pip-licenses --fail-on='GPL;AGPL;LGPL;SSPL' --partial-match` passes (the runtime tree stays BSD/MIT/Apache)
- [ ] Added/updated tests for this change
- [ ] Conventional commit message(s) (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`)

## Notes for reviewers

<!-- Anything that helps review: design choices, trade-offs, screenshots/renders for detection changes, etc. -->
