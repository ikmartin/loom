"""The errors loom raises to refuse something, and the exit code each gives a command.

Exit codes: 0 success, 1 a content problem the author can fix in the source, 2 a usage or environment problem.
"""

from __future__ import annotations

import click

EXIT_CONTENT = 1
EXIT_USAGE = 2


#: What click prints before a refusal's first line, which `fit` leaves room for.
ERROR_LEAD = len("Error: ")


def fit(text: str, lead: int = 0) -> str:
    """`text` within 100 columns line by line (T5), its first line `lead` shorter for a prefix printed before it.

    The refusals' and notes' one wrapper; an identifier or path longer than the width stands alone on its line, never cut.
    """
    from loom.cli.report import WIDTH, wrap

    return "\n".join(w for i, line in enumerate(text.split("\n")) for w in wrap(line, WIDTH - (lead if i == 0 else 0)))


class ContentError(click.ClickException):
    """A problem in the quilt's content (lint errors, failed identity test, refused write). Exit 1.

    The message is wrapped to fit; `verbatim` follows it as given, for text whose lines are its content, such as a diff.
    """

    exit_code = EXIT_CONTENT

    def __init__(self, message: str, verbatim: str = "") -> None:
        super().__init__(message)
        self.verbatim = verbatim

    def format_message(self) -> str:
        return fit(self.message, ERROR_LEAD) + self.verbatim


class EnvError(click.ClickException):
    """A usage or environment problem (bad arguments, missing tool, no author name). Exit 2.

    The message is wrapped to fit; `verbatim` follows it as given, for text whose lines are its content.
    """

    exit_code = EXIT_USAGE

    def __init__(self, message: str, verbatim: str = "") -> None:
        super().__init__(message)
        self.verbatim = verbatim

    def format_message(self) -> str:
        return fit(self.message, ERROR_LEAD) + self.verbatim


class NoNameError(EnvError):
    """A write recorded under the person's name, refused while no source gives one (`scan.quilt.resolve_author`); the write API answers it 409 `no-reviewer`."""


class NotFoundError(EnvError):
    """An argument names something that does not exist: a node, an annotation, a session, a cited work, a result. Exit 2, like any argument that names nothing; the write API answers it 404 `no-such-<what>`."""

    def __init__(self, what: str, message: str) -> None:
        super().__init__(message)
        self.what = what
