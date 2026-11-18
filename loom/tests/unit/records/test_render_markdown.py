"""`render_markdown`: an annotation's or a message's Markdown as HTML, with its TeX lifted out before Commonmark sees it (plan 0.11 Part A)."""

from __future__ import annotations

from loom.records.store import render_markdown


def test_math_survives_markdown() -> None:
    """Commonmark has no math: `$a_i b_i$` loses both subscripts to emphasis unless the TeX is lifted out first."""
    out = render_markdown("The bound $O(n^2)$ is sharp for $a_i b_i$ when *this* holds.")
    assert '<span class="math inline">\\(O(n^2)\\)</span>' in out
    assert '<span class="math inline">\\(a_i b_i\\)</span>' in out  # not <em>i b</em>
    assert "<em>this</em>" in out  # emphasis outside the math still works


def test_math_is_escaped_for_html() -> None:
    out = render_markdown("Compare $x < y$ and $a \\& b$.")
    assert "&lt;" in out and "&amp;" in out


def test_display_math_is_a_block_not_a_div_inside_a_paragraph() -> None:
    """A sentence, a newline, `$$…$$`, a newline and another sentence is how an annotation is written; an equation inside the paragraph's `<p>` is not HTML, and a browser fixes it by closing the paragraph early."""
    out = render_markdown("The bound $n \\le 2$ needs it, and then\n$$\\int_0^1 f$$\nfollows.")
    assert out.count("<p>") == out.count("</p>") == 2
    before, after = out.split('<div class="math display">\\[\\int_0^1 f\\]</div>')
    assert before.rstrip().endswith("</p>")  # the paragraph is closed before the equation, not around it
    assert out.index('<span class="math inline">') < out.index('<div class="math display">')
    assert out.rstrip().endswith("<p>follows.</p>")
    # and a display set off by a blank line is the same block
    apart = render_markdown("Then:\n\n$$\\int_0^1 f = 1$$\n")
    assert '<div class="math display">\\[\\int_0^1 f = 1\\]</div>' in apart and "<p><div" not in apart


def test_dollar_amounts_stay_text() -> None:
    """QF-19: a sentence about prices drew as one span of mathematics. Pandoc's rule decides: an opening `$` has a non-space character to its right, a closing one a non-space character to its left and no digit right after it."""
    sentence = "A trader pays $5 for one share and sells it for $7 the next day."
    assert render_markdown(sentence) == f"<p>{sentence}</p>"
    for text in ("It cost $20,000 then and $30,000 now.", "From $5 to $ 7.", "Pay $x$5 now.", "$5\n\nand $7"):
        assert '<span class="math' not in render_markdown(text), text
    # `\$` is a dollar sign, and mathematics beside it still draws
    escaped = render_markdown("It costs \\$5, and $x$ of them cost \\$5$x$.")
    assert "It costs $5, and " in escaped and escaped.count('<span class="math inline">\\(x\\)</span>') == 2


def test_mathematics_still_draws_under_pandoc_s_rule() -> None:
    def inline(tex: str) -> str:
        return f'<span class="math inline">\\({tex}\\)</span>'

    assert render_markdown("$x$") == f"<p>{inline('x')}</p>"
    assert inline("a + b") in render_markdown("Take $a + b$ here.")
    assert render_markdown("$f(x)$ and $g(y)$") == f"<p>{inline('f(x)')} and {inline('g(y)')}</p>"
    assert '<div class="math display">\\[\\int_0^1 f = 1\\]</div>' in render_markdown(
        "Then\n$$\n\\int_0^1 f = 1\n$$\nfollows."
    )
    # a closing `$` at the end of a line, and at the end of the text
    ends = render_markdown("The sum is $a+b$\nand the product $ab$")
    assert inline("a+b") in ends and inline("ab") in ends
    # a `$` escaped inside a span is the span's own
    assert inline("a \\$ b") in render_markdown("Write $a \\$ b$.")


def test_a_dollar_amount_moves_no_box_off_its_line() -> None:
    """The task items' lines come from the same reading of `$` as the page (`source_line`): an amount read as a span across lines would have swallowed the first box and put every later line out."""
    from loom.tasks import items

    text = "A trader pays $5 for one share.\n\n- [ ] sell it for $7\n- [x] count $n$ handles\n"
    assert [(t.line, t.done) for t in items(text)] == [(2, False), (3, True)]


def test_code_is_quoted_as_written() -> None:
    """F11 of the 0.14 study: a quote of source in backticks had its `$…$` turned into `\\(…\\)`."""
    got = render_markdown("Quote: `Let $\\quiv$ be` and $x$.")
    assert "<code>Let $\\quiv$ be</code>" in got and '<span class="math inline">\\(x\\)</span>' in got


def test_a_table_renders_as_a_table_with_its_math_typeset() -> None:
    """An agent's comparison table arrived in the chat as one run-on paragraph of pipes: CommonMark has no tables, and the renderer was CommonMark alone."""
    text = "| They cite | Current draft |\n|:---|---:|\n| [GM, Lem. 2.16] | replace $T$ by a cover |\n| [GM, Lem. 3.11] | matches |\n"
    out = render_markdown(text)
    assert "<table>" in out and out.count("<tr>") == 3 and "<th>They cite</th>" in out
    assert '<span class="math inline">\\(T\\)</span>' in out
    assert "style=" not in out and "|" not in out
