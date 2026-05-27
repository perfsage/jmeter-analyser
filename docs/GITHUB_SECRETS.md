# One-time setup for CI/CD

## GitHub repository secrets

Add these under **Settings → Secrets and variables → Actions** in `perfsage/jmeter-analyser`:

| Secret | Description |
|--------|-------------|
| `DOCKERHUB_USERNAME` | Docker Hub username (e.g. `perfsage`) |
| `DOCKERHUB_TOKEN` | Docker Hub access token ([create here](https://hub.docker.com/settings/security)) |

## What happens on push

| Event | CI | Docker Publish |
|-------|-----|----------------|
| Push to `main` | Ruff, mypy, pytest | Builds multi-arch image → `perfsage/jmeter-analyser:latest`, `:0.1.0`, `:sha-…` |
| Tag `v*` | Same | Also pushes semver tag (e.g. `:0.1.0`) |
| Pull request | CI only | — |

Docker Hub README is synced from [`docs/DOCKERHUB.md`](DOCKERHUB.md) on every publish.

## Release checklist

1. Update [`VERSION`](../VERSION) and [`CHANGELOG.md`](../CHANGELOG.md)
2. Commit: `git commit -m "release: v0.1.0"`
3. Tag: `git tag v0.1.0 && git push origin main --tags`
