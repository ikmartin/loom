import pytest

from loom.scan.tokenize import (
    CACHED_FROM,
    OUTLINE_CMDS,
    commands,
    env_tree,
    match_group,
    outline,
    read_args,
    read_optional,
    tokenize,
)


def kinds(text: str) -> list[tuple[str, str]]:
    return [(t.kind, t.value) for t in tokenize(text)]


def test_tokenize_basic_forms() -> None:
    toks = kinds(r"a \emph{b} $x$ \[y\] \\ 10\% {c}")
    assert ("cmd", "emph") in toks
    assert ("open", "{") in toks and ("close", "}") in toks
    assert ("math", "$") in toks and ("math", "\\[") in toks and ("math", "\\]") in toks
    assert ("cmd", "\\") in toks and ("cmd", "%") in toks


def test_tokenize_begin_end_and_verbatim() -> None:
    text = "\\begin{lemma}[T]\nx\n\\end{lemma}\n\\begin{verbatim}\\begin{fake}\\end{verbatim}"
    toks = tokenize(text)
    assert [t.value for t in toks if t.kind == "begin"] == ["lemma", "verbatim"]
    assert [t.value for t in toks if t.kind == "end"] == ["lemma", "verbatim"]
    verb = [t for t in toks if t.kind == "verbatim"]
    assert verb and verb[0].value == "\\begin{fake}"


def test_tokenize_verb_command() -> None:
    toks = tokenize(r"see \verb|\begin{x}| here")
    assert [t.value for t in toks if t.kind == "verb"] == ["\\begin{x}"]
    assert not [t for t in toks if t.kind == "begin"]


def test_match_group_crosses_newlines_and_escapes() -> None:
    text = "\\cite{Parker: reg,Parker:\ncmp} tail"
    start = text.index("{")
    end = match_group(text, start)
    assert text[start:end] == "{Parker: reg,Parker:\ncmp}"
    text2 = r"{a \{ b} c"
    assert text2[0 : match_group(text2, 0)] == r"{a \{ b}"


def test_read_optional_not_across_blank_line() -> None:
    assert read_optional("\\begin{x}[T] y", 9)[0] == "T"
    assert read_optional("\\begin{x}\n[T] y", 9)[0] == "T"
    assert read_optional("\\begin{x}\n\n[T] y", 9)[0] is None


def test_read_args_spec() -> None:
    text = r"\newtheorem{lem}[thm]{Lemma}"
    values, spans, pos = read_args(text, len(r"\newtheorem"), "mom")
    assert values == ["lem", "thm", "Lemma"]
    assert text[spans[2][0] : spans[2][1]] == "Lemma"
    assert pos == len(text)


def test_env_tree_nesting_and_problems() -> None:
    text = "\\begin{proof}\nA\n\\begin{lemma}\\label{x}\nB\n\\end{lemma}\n\\begin{proof}\nC\n\\end{proof}\n\\end{proof}\n\\end{stray}"
    roots, problems = env_tree(text)
    assert [r.name for r in roots] == ["proof"]
    assert [c.name for c in roots[0].children or []] == ["lemma", "proof"]
    assert problems == [("end-without-begin", text.index("\\end{stray}"), "stray")]
    roots2, problems2 = env_tree("\\begin{lemma}\nno end")
    assert problems2 == [("unclosed", 0, "lemma")]


def test_an_outline_is_the_boundaries_and_file_commands_tokenize_finds() -> None:
    text = (
        "\\documentclass{amsart}\\usepackage{x}\n\\begin{document}\\input{a} \\verb|\\input{b}| \\emph{c}\n"
        "\\begin{verbatim}\\include{d}\\end{verbatim}\\nest{e} \\includegraphics{f}\\end{document}\n"
    )
    assert [(t.kind, t.value) for t in outline(text)] == [
        ("cmd", "documentclass"),
        ("cmd", "usepackage"),
        ("begin", "document"),
        ("cmd", "input"),
        ("begin", "verbatim"),
        ("end", "verbatim"),
        ("cmd", "nest"),
        ("cmd", "includegraphics"),
        ("end", "document"),
    ]
    long = text * 100  # long enough to be remembered
    assert len(long) >= CACHED_FROM
    kept = [t for t in tokenize(long) if t.kind in ("begin", "end") or t.kind == "cmd" and t.value in OUTLINE_CMDS]
    assert list(outline(long)) == kept
    assert [t.value for t in commands(long, ("input", "nest"))] == ["input", "nest"] * 100


def test_commands_refuses_a_name_an_outline_does_not_keep() -> None:
    with pytest.raises(ValueError, match="emph"):
        commands("\\emph{x}", ("input", "emph"))
