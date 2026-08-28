from __future__ import annotations

from project_lens.readme_audit import classify_readme, verdict_label


def test_classify_missing_when_none():
    assert classify_readme(None) == "missing"


def test_classify_missing_when_blank():
    assert classify_readme("   \n\t  ") == "missing"


def test_classify_template_when_sveltekit_scaffold():
    """실제로 qr-gen에서 발견한 사례 — sv create 기본 README 그대로."""

    content = "# sv\n\nEverything you need to build a Svelte project, powered by `sv`.\n"
    assert classify_readme(content) == "template"


def test_classify_template_overrides_length():
    # 스캐폴드 문구가 있으면 길이가 충분해도 template으로 분류돼야 한다.
    content = "everything you need to build a svelte project" + " padding" * 100
    assert classify_readme(content) == "template"


def test_classify_thin_when_short():
    assert classify_readme("# my-project\n\nTODO\n") == "thin"


def test_classify_ok_when_long_and_no_scaffold_markers():
    content = "# base64-code\n\n" + ("실제 프로젝트 설명입니다. " * 40)
    assert classify_readme(content) == "ok"


def test_verdict_label_known_and_unknown():
    assert verdict_label("missing") == "README 없음"
    assert verdict_label("something-new") == "something-new"
