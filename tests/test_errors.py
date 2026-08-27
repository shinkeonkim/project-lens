from __future__ import annotations

from project_lens.errors import short


def test_short_returns_first_line_only():
    exc = Exception("line one\nline two\nline three")
    assert short(exc) == "line one"


def test_short_returns_whole_message_when_single_line():
    exc = Exception("just one line")
    assert short(exc) == "just one line"
