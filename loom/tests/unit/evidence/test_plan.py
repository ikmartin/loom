"""The plan for asking an agent to formalize (`evidence.plan`), by its four rules, over a small web of the person's results and the library's, in which a draft's result reaches the library as it will once citations resolve to nodes."""

from __future__ import annotations

from loom.evidence.plan import Item, plan
from loom.evidence.status import Status
from loom.evidence.subjects import Subject

#: key: (mine, named, stated, lean, reading, statement uses, proof uses)
WEB: dict[str, tuple[bool, bool, bool, str, str | None, list[str], list[str]]] = {
    "thm": (True, True, False, "none", None, ["def:a"], ["lem:b", "lem:c"]),
    "def:a": (True, True, True, "none", None, ["lib-def"], []),
    "lem:b": (True, True, False, "none", None, ["lib-stub"], ["lem:deep"]),
    "lem:c": (True, False, False, "none", None, ["lib-ok"], []),
    "lem:deep": (True, True, False, "none", None, [], []),
    "lib-def": (False, True, True, "none", "unchecked", [], []),
    "lib-stub": (False, True, False, "none", "stub", [], []),
    "lib-ok": (False, True, False, "unattested", "matches", ["lib-used"], []),
    "lib-used": (False, True, False, "none", "matches", [], []),
    "done": (True, True, False, "formalized", None, ["lem:hidden"], []),
    "lem:hidden": (True, True, False, "none", None, [], []),
    "waits": (True, True, False, "unattested", None, ["lem:hidden"], []),
    "moved": (True, True, False, "changed", None, [], []),
}


def item(key: str) -> Item:
    mine, named, stated, lean, reading, *_ = WEB[key]
    return Item(key, mine, named, stated, Status(Subject("node", "tq-0000", "sha256:" + "0" * 64), reading, lean=lean))


def uses(key: str) -> tuple[list[str], list[str]]:
    return WEB[key][5], WEB[key][6]


def test_a_target_to_prove_reaches_all_it_uses_and_the_library_as_state_prove_and_assume() -> None:
    found = plan(["thm"], [], item, uses)
    assert found.state == ["def:a", "lib-def"]
    assert found.prove == [("lem:b", False), ("lem:c", False), ("lem:deep", False)]
    assert found.assume == [("lib-stub", "not-read"), ("lib-ok", None), ("lib-used", None)]


def test_only_a_missing_label_stops_a_request_and_what_is_unread_or_unchecked_stands_before() -> None:
    found = plan(["thm"], [], item, uses)
    assert found.stops == ["lem:c"]
    assert found.before == {"not-read": ["lib-stub"], "not-checked": ["lib-def"], "attest": ["lib-ok"], "attested-changed": []}  # fmt: skip


def test_a_result_assumed_for_now_or_stated_is_followed_by_its_statement_alone() -> None:
    found = plan(["thm"], ["lem:b"], item, uses)
    assert ("lem:b", True) in found.prove and ("lem:deep", False) not in found.prove
    assumed_target = plan(["thm"], ["thm"], item, uses)
    assert assumed_target.prove == [] and assumed_target.state == ["def:a", "lib-def"]


def test_what_is_formalized_or_waits_for_the_persons_word_is_listed_and_not_followed() -> None:
    WEB["top"] = (True, True, False, "none", None, ["done", "waits", "moved"], [])
    try:
        found = plan(["top"], [], item, uses)
    finally:
        del WEB["top"]
    assert found.formalized == ["done"] and found.before["attest"] == ["waits"]
    assert found.before["attested-changed"] == ["moved"] and found.prove == []


def test_a_target_without_a_label_stops_the_request() -> None:
    assert plan(["lem:c"], [], item, uses).stops == ["lem:c"]
