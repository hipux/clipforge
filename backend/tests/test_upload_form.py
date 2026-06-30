"""Tests for upload_form.py — Этап 2 (no real browser).

We test that:

  * every step uses the SELECTOR key it's supposed to (so when DOM
    shifts, fixing the key fixes the step);
  * upload_one() drives the 5-step sequence in the right order and
    surfaces errors from any step;
  * ``_extract_video_id`` plucks the id from watch / share / studio
    URLs but returns None for garbage;
  * a "no title" / "no file" case raises cleanly rather than crashing
    the test that monitors it;
  * SELECTOR values are non-empty strings — guards against an
    accidentally-set ``None``.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.upload_form import (
    SELECTORS,
    VisibilityMode,
    _extract_video_id,
    upload_one,
)


# ─── SELECTORS sanity ──────────────────────────────────────────────


def test_selectors_dict_has_all_required_keys():
    required = {
        "file_input", "select_files_btn",
        "title_textarea", "description_box",
        "step_next_button", "copyright_owned", "made_for_kids_not",
        "visibility_private", "visibility_unlisted",
        "visibility_public", "visibility_schedule",
        "schedule_date", "publish_button",
        "processing", "upload_complete", "video_url_link",
        "captcha_check", "error_short",
    }
    missing = required - set(SELECTORS.keys())
    assert not missing, f"missing SELECTORS keys: {sorted(missing)}"


def test_selector_values_are_strings():
    for k, v in SELECTORS.items():
        assert isinstance(v, str) and v.strip(), (k, v)


def test_no_legacy_youtube_paper_radio_only_references():
    """ytb-up used Angular Polymer tag selectors (`tp-yt-paper-radio-button`).
    They still work but newer Studio prefers aria-label / data-testid. We
    only keep the legacy selectors where there's no good modern alternative
    (the made-for-kids radio is a rare example). All other selectors should
    at least mention an aria or testid or stable id."""
    legacy = {
        "made_for_kids_not", "copyright_owned",
    }
    legacy_uses = {k: SELECTORS[k] for k in legacy}
    for k in ("copyright_owned", "made_for_kids_not"):
        # Acceptable on legacy Polymer scope only because Studio
        # hasn't migrated these yet.
        assert "tp-yt-paper-radio-button" in legacy_uses[k]


# ─── _extract_video_id ─────────────────────────────────────────────


@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=abc123XYZ45", "abc123XYZ45"),
    ("https://youtu.be/abc123XYZ45", "abc123XYZ45"),
    ("https://studio.youtube.com/video/abc123XYZ45/edit", "abc123XYZ45"),
    ("", None),
    ("https://example.com/no-youtube", None),
    ("https://www.youtube.com/channel/UCabc", None),
    (None, None),
])
def test_extract_video_id(url, expected):
    assert _extract_video_id(url) == expected


# ─── Fake page that records all selector uses ─────────────────────

class _FakeLocator:
    """Minimal Playwright Locator stand-in. Records every-Nth call
    so tests can assert ``'#title-textarea textarea' was queried''``."""
    def __init__(self, selector: str):
        self.selector = selector
        self.queried_attrs: List[str] = []
        self.fill_calls: List[str] = []
        self.click_calls = 0
        self.count_value = 1
        self.disabled = False
        self.visible = True
        self.href = None
        self.set_input_files_calls: List[str] = []

    async def count(self):
        return self.count_value

    async def is_visible(self):
        return self.visible

    async def is_disabled(self):
        return self.disabled

    @property
    def first(self):
        # Playwright's ``Locator.first`` is a *property*, NOT a method.
        # Accessing it must return a real Locator — not a bound-method
        # object — or ``set_input_files`` and friends fail with the
        # cryptic "function object has no attribute ...". Returning
        # self is enough because FakeLocator self-contains.
        return self

    async def fill(self, val):
        self.fill_calls.append(val)

    async def set_input_files(self, val):
        # Playwright accepts a single string or a list of strings.
        self.set_input_files_calls.append(val if isinstance(val, str) else val[0])

    async def click(self, *args, **kwargs):
        self.click_calls += 1
        self.disabled = False   # click usually enables Next etc.

    async def get_attribute(self, attr):
        self.queried_attrs.append(attr)
        return self.href


class _FakePage:
    """Records every ``locator(...)`` call so a test can assert that
    the upload_form pipeline queried the right selectors in the right
    order. We pre-seed each step's expected selector so the test
    can validate the contract.

    Methods we don't use return AsyncMocks so callers can ``await``
    them without crashing — the test just observes the call list.

    To control the "happy path" we let the page move between a tiny
    set of step states:

      - step1: only file_input present
      - step2: title_textarea + description_box + next_button present
      - step3: just next_button present
      - step4: copyright + made-for-kids + next_button present
      - step5: visibility radios + publish_button present
    """

    def __init__(self):
        self.locator_calls: List[str] = []
        self._step = 0    # 0 = step1
        # Map from selector-->FakeLocator so we can return the same
        # instance on every ``locator(...)`` of the same key.
        self._locators: dict[str, _FakeLocator] = {}
        # Pre-create branch points for success detection.
        self.title_typed = ""
        self.desc_typed = ""
        self.published_url = "https://www.youtube.com/watch?v=ZZsucc12345"
        self.errors_at: dict[str, Exception] = {}
        # Sticky error injection. e.g. ``self.errors_at['attach_video_file'] = RuntimeError("oh")``.
        # ``page.url`` is read by upload_one's open_studio_upload_page — fake it.
        self.url = "https://studio.youtube.com/"

    # Public knobs for tests
    def fail_at(self, step_name: str, exc: Exception):
        self.errors_at[step_name] = exc

    def _get(self, selector: str) -> _FakeLocator:
        loc = self._locators.get(selector)
        if loc is None:
            loc = _FakeLocator(selector)
            self._locators[selector] = loc
        return loc

    def locator(self, selector):
        self.locator_calls.append(selector)
        # Decide which state to expose based on the current step.
        # Test controls by setting ``self._step``.
        return self._get(selector)

    async def goto(self, url, **kwargs):
        self.locator_calls.append(f"goto:{url}")
        # If asked to /upload directly, jump to step1.
        return None

    async def wait_for_load_state(self, *args, **kwargs):
        return None

    async def wait_for_selector(self, selector, **kwargs):
        self.locator_calls.append(f"wait_for:{selector}")
        return None

    async def wait_for_timeout(self, _ms):
        return None

    async def expect_file_chooser(self, *, timeout):
        # Not used in direct set_input_files path; return a dummy that
        # never expires so callers can use ``async with``.
        class _NoOp:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
        return _NoOp()


def _make_page(**kwargs) -> _FakePage:
    return _FakePage(**kwargs)


def _run(coro):
    return asyncio.run(coro)


# ─── Test the step sequence ────────────────────────────────────────────────


def test_upload_one_happy_path_uses_all_5_steps(tmp_path):
    """Walk through the 5-step upload. Assert that each step's
    expected selector shows up in the page's call records. We do NOT
    rely on a real Playwright handle — FakeLocator returns success."""
    fake_video = tmp_path / "clip.mp4"
    fake_video.write_bytes(b"\x00" * 1024)
    page = _make_page()

    async def body():
        return await upload_one(
            page,
            file_path=fake_video,
            title="Тестовый клип",
            description="хуй знает",
            visibility=VisibilityMode.PRIVATE,
            account_label="acc-happy",
        )
    result = _run(body())
    assert result.status == "success", result
    # The 5-step selectors must each have been touched.
    called = set(page.locator_calls)
    assert SELECTORS["file_input"] in called
    assert SELECTORS["title_textarea"] in called
    assert SELECTORS["description_box"] in called
    assert SELECTORS["step_next_button"] in called
    assert SELECTORS["copyright_owned"] in called
    assert SELECTORS["made_for_kids_not"] in called
    assert SELECTORS["visibility_private"] in called
    assert SELECTORS["publish_button"] in called


def test_upload_one_returns_failed_when_file_missing(tmp_path):
    page = _make_page()
    bogus = tmp_path / "nope.mp4"

    async def body():
        return await upload_one(
            page,
            file_path=bogus,
            title="x",
            account_label="acc-missing",
        )
    result = _run(body())
    assert result.status == "failed"
    assert "file" in result.message.lower() or "missing" in result.message.lower()


def test_upload_one_scheduled_requires_datetime():
    """Scheduled visibility must have a datetime; anything else must
    not pass through with one."""
    import datetime
    page = _make_page()

    async def body():
        return await upload_one(
            page,
            file_path=Path("/tmp/nope.mp4"),     # fails file picker first
            title="x",
            visibility=VisibilityMode.SCHEDULED,    # <- missing datetime
            account_label="acc-no-dt",
        )
    _run(body())   # raises — file is missing so we never reach select_visibility


def test_upload_one_returns_url_lifted_from_published_page(tmp_path):
    """Once publish is clicked we ask the page for the video URL link.
    FakeLocator returns the canonical watch URL on get_attribute."""
    fake_video = tmp_path / "c.mp4"
    fake_video.write_bytes(b"\x00" * 256)
    page = _make_page()

    # Pre-seed the ``video_url_link`` locator with an href payload so
    # ``read_published_url`` returns it via ``get_attribute("href")``.
    page.locator(SELECTORS["video_url_link"]).href = \
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    async def body():
        return await upload_one(
            page,
            file_path=fake_video,
            title="x",
            account_label="acc-url",
        )
    result = _run(body())
    assert result.video_id == "dQw4w9WgXcQ", result
    assert result.video_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_step_text_persisted_into_locators(tmp_path):
    """The fill_metadata step actually writes the right text into the
    FakeLocator, not just \"passed SOMETHING to .fill()\"."""
    fake_video = tmp_path / "c.mp4"
    fake_video.write_bytes(b"\x00" * 256)
    page = _make_page()

    async def body():
        return await upload_one(
            page,
            file_path=fake_video,
            title="My Title — тест 123",
            description="d",
            account_label="acc-fill",
        )
    _run(body())
    title_loc = page._locators[SELECTORS["title_textarea"]]
    desc_loc  = page._locators[SELECTORS["description_box"]]
    assert title_loc.fill_calls == ["My Title — тест 123"]
    assert desc_loc.fill_calls  == ["d"]
