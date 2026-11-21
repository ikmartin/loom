from pathlib import Path

from loom.scan.bib import citekey_slug, parse_bib

BIB = r"""
@comment{ignored}
@string{jams = "J. Amer. Math. Soc."}
@article{Man12,
  author = {Manolache, Cristina},
  title = {Virtual pull-backs},
  year = 2012,
  eprint = {0805.2065v2},
  journal = jams # {, extra},
}
@book(stacks-project, author="The Stacks Project Authors", title={{Stacks} Project}, url={https://stacks.math.columbia.edu})
@misc{Parker: gluing,
 title = {Gluing}}
"""


def test_bib_entries_and_fields() -> None:
    entries = parse_bib(BIB)
    assert set(entries) == {"Man12", "stacks-project", "Parker: gluing"}
    man = entries["Man12"]
    assert man.type == "article"
    assert man.fields["author"] == "Manolache, Cristina"
    assert man.fields["year"] == "2012"
    assert man.eprint == "0805.2065v2" and man.version == "2"
    assert entries["stacks-project"].fields["title"] == "{Stacks} Project"


def test_citekey_slug() -> None:
    assert citekey_slug("stacks-project") == "stacksproject"
    assert citekey_slug("Parker: gluing") == "Parkergluing"
    assert citekey_slug("Man12") == "Man12"


def test_the_quilts_citekeys_are_its_references_keys(tmp_path: Path) -> None:
    """An author's `.bib`, a source's, a run's: none gives the scan a citekey; the library's references do, each entry's key to its reference."""
    from tests.unit.scan.helpers import PREAMBLE, make_quilt

    owned = '+++\nschema = 1\nid = "tq-00A1-ref"\ntaxon = "reference"\n+++\n@book{Owned, title={Owned}}\n'
    result = make_quilt(
        tmp_path,
        {
            "drafting/main.tex": PREAMBLE + "\\begin{document}\n\\end{document}\n",
            "refs.bib": "@book{Author, title={Mine}}\n",
            "refs/arxiv/1/src/theirs.bib": "@book{Theirs, title={Theirs}}\n",
            ".loom/library/nodes/tq-00A1-ref.node": owned,
        },
    )
    assert set(result.bib) == {"Owned"} and result.refs == {"Owned": "tq-00A1-ref"}
