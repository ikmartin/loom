"""The library's part of a build: gathering, which makes a reference for each entry the documents and landmarks read that the library lacks, and says each entry it cannot keep among the diagnostics; and `arriving`, the drops that wait on the person. The works an agent suggests and what the library's page reads of each work are not built yet (docs/specs/reserved.md)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loom.render.attach import Attaching


def attach(build: Attaching) -> None:
    """Say each entry the build's gathering (`library.gather`, run before the fragments with the stubs the drafts' citations want) could not keep, as a `loom:bib-entry-refused` diagnostic; then add `arriving`: each drop that waits, a question or a file received and not yet taken, as the intake's row (specs/manifest.md §1); empty when none does."""
    from loom.library.gather import gather, problems
    from loom.library.intake import waiting

    done = build.gathered if build.gathered is not None else gather(build.result)
    build.manifest["diagnostics"] += [d.to_dict() for d in problems(build.result, done)]
    build.manifest["arriving"] = waiting(build.result.quilt.root)
