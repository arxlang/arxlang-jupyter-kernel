## Description

Please include a summary of the change, motivation, and relevant context. If
this resolves an open issue, link it below.

Fixes #(issue)

## Type of Change

Please mark the relevant option with an `x`:

- [ ] `fix`: Bug fix (non-breaking change which fixes an issue; bumps PATCH
      version)
- [ ] `feat`: New feature (non-breaking change which adds functionality; bumps
      MINOR version)
- [ ] `chore`: Tooling, dependency, or configuration changes
- [ ] `docs`: Documentation update
- [ ] `test`: Adding or correcting tests
- [ ] `refactor`: Code change that neither fixes a bug nor adds a feature
- [ ] `BREAKING CHANGE`: Breaking change that requires users to modify existing
      setups (bumps MAJOR version)

## Checklist

- [ ] My PR title follows
      [Conventional Commits](https://www.conventionalcommits.org/) (e.g.
      `fix: ...`, `feat: ...`, `chore: ...`) for semantic release.
- [ ] I have added or updated tests for my changes.
- [ ] All tests pass locally (`makim tests.unit` or `poetry run pytest`).
- [ ] Code coverage remains >= 90% (`--cov-fail-under=90`).
- [ ] Pre-commit hooks pass locally (`pre-commit run --all-files` or
      `makim tests.linter`).
- [ ] Relevant documentation has been updated.
