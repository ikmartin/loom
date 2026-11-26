# WQ-19 · Publishing to PyPI and npm

**Repo:** loom, viewer

## Trigger

The author decides to release.

## Why deferred

Publishing is the author's act and never an agent's — a standing rule in `AGENTS.md`. A release is a GitHub release, which the install line reads (`loom/docs/RELEASE.md`); nothing is published to a package index.

## Rough design

Follow `loom/docs/RELEASE.md`, then publish the wheel its release workflow built (`uv publish`). [[WQ-16]] supplies the Overleaf result the release notes want.

The distribution is `loomtex` on PyPI; the viewer ships inside it as a vendored bundle, so end users need neither the viewer's sources nor Node.

## Blast radius

`loom/docs/RELEASE.md`, version numbers in both repositories, the release notes.

## Related

[[WQ-16]], [[WQ-17]]; `loom/docs/RELEASE.md`; `closed/M7.md`.
