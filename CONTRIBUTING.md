# Contributing to acroforge

Thanks for your interest! acroforge turns flat PDFs into real, fillable AcroForms.
Contributions are welcome - please read this first so your PR goes smoothly.

## Project philosophy (please respect it)

- **The engine is bulletproof; detection is best-effort.** `build` / `fill` / `flatten`
  must be deterministic and correct for every valid input. The `detect` layer is
  allowed to be heuristic and confidence-scored - but it must never make the engine
  unreliable.
- **Zero copyleft.** The runtime dependency tree must stay permissive (BSD / MIT /
  Apache). **No GPL / AGPL / LGPL / SSPL** dependencies - CI enforces this and your PR
  will fail the license gate if one sneaks in (even transitively).
- **No AI in the core.** Detection is pure deterministic geometry - no models, no
  network calls.
- **Stay narrow.** acroforge does one thing. New features need a clear case.

## Development setup

Requires Python 3.11+ and [`uv`](https://docs.astral.sh/uv/). The cross-viewer test
harness additionally needs Node 22.13+.

```bash
git clone https://github.com/<your-fork>/acroforge
cd acroforge
uv venv
uv pip install -e ".[dev,harness]"
# (the harness's pdf.js renderer also needs: cd harness && npm install)
```

## Before you open a PR

Run the full quality bar locally - all of it must be green:

```bash
uv run ruff check src tests      # lint
uv run mypy src                  # types (strict)
uv run pytest                    # tests
uv run pip-licenses --fail-on='GPL;AGPL;LGPL;SSPL' --partial-match   # license gate
```

- **Add tests** for any behavior change (we use TDD - write the failing test first).
- **Keep `mypy --strict` clean.**
- **Conventional commit messages** (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`).

## Workflow

1. **Fork** the repo and create a branch (`git checkout -b feat/my-change`).
2. Make your change with tests.
3. Run the quality bar above.
4. Open a **Pull Request** against `main`. CI (lint + types + tests + license gate)
   runs automatically.
5. A maintainer reviews and merges. Thanks!

## Reporting bugs / ideas

Open an issue. For detection misses, attaching a **non-sensitive** sample PDF (no real
PII) that reproduces the problem helps a lot.

## License

By contributing, you agree your contributions are licensed under the project's
[Apache-2.0](LICENSE) license.
