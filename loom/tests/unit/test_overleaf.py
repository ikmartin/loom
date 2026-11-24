"""The Overleaf mirror, against local stand-ins for Overleaf: a bare repository, and a local git server behind a password for the token's paths."""

from __future__ import annotations

import pytest

from loom.overleaf import LinkRefused, address

ID = "5f1e0c2a9b3d4e6f7a8b9c0d"

# ---- the link --------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "link",
    [
        f"https://www.overleaf.com/project/{ID}",
        f"https://www.overleaf.com/project/{ID}/",
        f"https://www.overleaf.com/project/{ID}?utm=x#section",
        f"www.overleaf.com/project/{ID}",
        f"overleaf.com/project/{ID.upper()}",
        f"https://git.overleaf.com/{ID}",
        f"https://git@git.overleaf.com/{ID}",
        f"https://git.overleaf.com/{ID}.git",
        f"  git clone https://git.overleaf.com/{ID}  ",
        f"git clone https://git.overleaf.com/{ID} my-paper",
    ],
)
def test_a_project_s_own_link_in_any_form_overleaf_gives_names_its_git_address(link: str) -> None:
    assert address(link) == f"https://git.overleaf.com/{ID}"


def test_an_old_project_s_numeric_id_is_its_git_address() -> None:
    assert address("https://www.overleaf.com/project/1234567") == "https://git.overleaf.com/1234567"


@pytest.mark.parametrize(
    "link",
    [
        "https://www.overleaf.com/read/abcdefghijkl",
        "https://www.overleaf.com/read/abcdefghijkl#3f2a1b",
        "https://www.overleaf.com/8429385762qwertyzxcvbn",
    ],
)
def test_a_sharing_link_is_refused_because_it_does_not_name_the_project(link: str) -> None:
    with pytest.raises(LinkRefused) as refused:
        address(link)
    assert refused.value.code == "sharing-link"


@pytest.mark.parametrize(
    "link",
    [
        "",
        "https://www.overleaf.com/project",
        "https://www.overleaf.com/project/not-an-id",
        f"https://github.com/someone/{ID}",
        f"https://overleaf.example.edu/project/{ID}",
        f"https://git.overleaf.com.evil.example/{ID}",
        f"https://www.overleaf.com.evil.example/project/{ID}",
        "git clone",
    ],
)
def test_anything_else_is_refused_as_not_a_project(link: str) -> None:
    with pytest.raises(LinkRefused) as refused:
        address(link)
    assert refused.value.code == "not-a-project"
