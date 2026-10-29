"""Regression: higgsfield_video is retired and must never be routed into.

The wrapper posts to `platform.higgsfield.ai/v1/generations` with
`Authorization: Bearer <key>` plus an `X-API-Secret` header. Higgsfield does not
serve that shape — the live API is `api.higgsfield.ai`, a single
`Authorization: Key <key_id>:<secret>` header, and one path per model workflow.
Checked against the live service on 2026-10-27 with real credentials: the
wrapper's own endpoint answers `401 {"detail":"Invalid credentials"}`.

The trap was not the 401 itself, it was *when* it arrived. `get_status()`
returned AVAILABLE as soon as the two env vars existed, and the tool carried
`quality_score = 0.9` plus the full premium `supports` set, so
`video_selector` ranked it first for a cinematic brief and only found out after
it had committed to the provider. These tests pin all three legs: status,
refusal, and selectability — with credentials present, which is the case that
used to pass.

No network: `tests/conftest.py` blocks non-loopback sockets for the whole
session, so if `execute()` ever starts calling out again these tests fail with
`NetworkCallInTestError` rather than quietly passing.
"""

from __future__ import annotations

import pytest

from tools.base_tool import ToolStatus
from tools.video.higgsfield_video import HiggsFieldVideo


@pytest.fixture
def credentialed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The environment that used to make this tool look healthy."""
    monkeypatch.setenv("HIGGSFIELD_API_KEY", "key-id-placeholder")
    monkeypatch.setenv("HIGGSFIELD_API_SECRET", "secret-placeholder")
    monkeypatch.setenv("HIGGSFIELD_KEY", "key-id-placeholder:secret-placeholder")


def test_status_is_unavailable_even_with_credentials(credentialed: None) -> None:
    assert HiggsFieldVideo().get_status() is ToolStatus.UNAVAILABLE


def test_execute_refuses_and_names_the_replacement(credentialed: None) -> None:
    result = HiggsFieldVideo().execute(
        {"prompt": "a cinematic vertical teaser", "duration": "5"}
    )
    assert result.success is False
    assert "retired" in (result.error or "")
    # The caller must be told where to go instead, not just that this failed.
    assert "pixabay_video" in (result.error or "")
    assert result.artifacts == []
    assert result.cost_usd == 0.0


def test_fallbacks_lead_to_the_stock_source_route() -> None:
    # The stock-source adapters are the replacement path, and stock is first on
    # purpose — re-routing an explicit Higgsfield call to another premium
    # gateway would spend money the caller never asked for.
    assert HiggsFieldVideo.fallback_tools[0] == "pixabay_video"


def test_video_selector_will_not_select_it(credentialed: None) -> None:
    from tools.video.video_selector import VideoSelector

    selector = VideoSelector()
    inputs = {
        "prompt": "cinematic vertical teaser, character-consistent, 1080p",
        "operation": "text_to_video",
    }
    tool, _ = selector._select_best_tool(
        inputs, selector._providers(), selector._prepare_task_context(inputs)
    )
    assert tool is None or tool.name != "higgsfield_video"


def test_it_does_not_top_a_ranking(credentialed: None) -> None:
    """Rank mode does not filter on status, so the score itself has to be low.

    `video_selector` with `operation="rank"` returns every candidate it scored,
    available or not. A dead tool sitting at the top of that list is a
    recommendation an agent will act on, so `quality_score` and `supports` were
    zeroed out as well as the status.
    """
    from tools.video.video_selector import VideoSelector

    result = VideoSelector().execute(
        {
            "operation": "rank",
            "prompt": "cinematic vertical teaser, character-consistent, 1080p",
            "target_operation": "text_to_video",
        }
    )
    assert result.success
    rankings = result.data["rankings"]
    assert rankings, "nothing was ranked; the assertion below would be vacuous"
    assert rankings[0].get("tool_name") != "higgsfield_video"


def test_cost_estimate_is_not_an_order_of_magnitude_low() -> None:
    """The old table quoted $0.80 for a 5 s Seedance clip; it is $5.69.

    Measured from `POST api.higgsfield.ai/estimate/<endpoint_id>` on 2026-10-27:
    Seedance 2.5 at 1080p bills $1.1372 per second of output. Under-quoting is
    the direction that costs money, so this pins the floor rather than an exact
    figure.
    """
    tool = HiggsFieldVideo()
    assert tool.estimate_cost({"duration": "5"}) > 5.0
    assert tool.estimate_cost({"duration": "15"}) > 15.0
    # An unlisted model must not be cheaper than the dearest known one.
    assert tool.estimate_cost({"model": "sora_2", "duration": "5"}) == pytest.approx(
        tool.estimate_cost({"model": "seedance_2.0", "duration": "5"})
    )
