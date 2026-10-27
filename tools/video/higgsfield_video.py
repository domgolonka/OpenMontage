"""Higgsfield video generation — RETIRED. This wrapper never worked.

It was written against an API shape Higgsfield does not serve, so it reports
UNAVAILABLE and refuses to execute. Every line below is kept only so the
contract stays introspectable; nothing here reaches the network.

What it sends vs what the service accepts (re-checked 2026-10-27 with the
project's own working credentials in `.env`):

    this wrapper                            the live API
    ------------------------------------    ------------------------------------
    POST platform.higgsfield.ai             POST api.higgsfield.ai/<endpoint_id>
      /v1/generations                         one path per model workflow
    Authorization: Bearer <key>             Authorization: Key <key_id>:<secret>
      + X-API-Secret: <secret>                (one header)
    a `model` field, enum of names          no `model` field; model *is* the path
    GET /v1/generations/{id}                GET /requests/{id}/status
    (no cancel)                             POST /requests/{id}/cancel, refunds
    (no estimate)                           POST /estimate/<endpoint_id>, free

The auth scheme alone is fatal: posting to the wrapper's own endpoint with the
real key returns `401 {"detail":"Invalid credentials"}`, so no payload it builds
can ever be accepted. The wrapper also under-quoted cost by ~7x — see
`estimate_cost`.

Replacement route
-----------------
Stock footage via the stock-source adapters in `tools/video/stock_sources/`
(Pixabay video and Unsplash stills are the verified-working sources), reachable
as BaseTools through `pixabay_video` / `video_selector`. That is what
`fallback_tools` points at.

Why retire rather than rewrite: a real client needs the credential format, one
endpoint id per workflow, estimate-before-submit, status and cancel polling, and
a price table read from the estimate endpoint rather than hard-coded. That is a
new tool, not a patch. Retiring is the smaller, safer change — it removes a route
that fails only *after* the selector has committed to it.
"""

from __future__ import annotations

from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# Single source of truth for the default model. Referenced by both the input
# schema and every code path that reads `model`, so estimate_cost can never
# silently diverge from the advertised default again.
_DEFAULT_MODEL = "seedance_2.0"

_RETIRED = (
    "higgsfield_video is retired: it targets POST platform.higgsfield.ai/v1/generations "
    "with `Authorization: Bearer` + `X-API-Secret`, which the live service rejects with "
    "401 Invalid credentials. Use the stock-source route instead — pixabay_video, or "
    "tools/video/stock_sources/ via video_selector. A real Higgsfield client would need "
    "api.higgsfield.ai, one endpoint id per workflow, and estimate-before-submit; see "
    "the module docstring."
)


class HiggsFieldVideo(BaseTool):
    name = "higgsfield_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "higgsfield"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Nothing to install — higgsfield_video is retired and stays UNAVAILABLE even with "
        "HIGGSFIELD_API_KEY and HIGGSFIELD_API_SECRET set, because the endpoint it targets "
        "rejects them. Use pixabay_video, or tools/video/stock_sources/ via video_selector."
    )
    # No skill should route work here; the seedance-2-0 skill lists the gateways
    # that actually resolve.
    agent_skills = []

    capabilities: list[str] = []
    # Nothing is advertised as supported: the service has these features, this
    # wrapper cannot reach any of them. Leaving the premium flags set earned a
    # "premium cinematic" bonus in lib/scoring.py and put a dead tool first.
    supports = {
        "text_to_video": False,
        "image_to_video": False,
    }
    best_for = []
    not_good_for = [
        "anything — retired wrapper, written against an API shape Higgsfield does not serve",
    ]
    # The replacement route: the stock-source adapters, which are verified working.
    # Stock is deliberately first. Silently re-routing an explicit Higgsfield
    # request to another premium gateway would spend money the caller never asked
    # for, and this tool's own mis-quoting of cost is half the bug.
    fallback_tools = ["pixabay_video", "seedance_video", "seedance_replicate", "kling_video", "veo_video"]
    quality_score = 0.0

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "enum": [
                    "seedance_2.0",
                    "seedance_2.0_fast",
                    "kling_3.0",
                    "veo_3.1",
                    "sora_2",
                    "wan_2.5",
                    "soul_cinema",
                ],
                "default": _DEFAULT_MODEL,
                "description": (
                    "Never sent. The live API has no `model` field — the model is the URL path "
                    "(one endpoint id per workflow). Kept so estimate_cost stays introspectable."
                ),
            },
            "duration": {
                "type": "string",
                "enum": ["5", "10", "15"],
                "default": "5",
                "description": "Duration in seconds (availability varies by model)",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "21:9"],
                "default": "16:9",
            },
            "image_url": {"type": "string", "description": "Reference image URL for image_to_video"},
            "output_path": {"type": "string"},
        },
    }

    # Consumes nothing and opens no socket: execute() returns a refusal.
    resource_profile = ResourceProfile(
        cpu_cores=0, ram_mb=0, vram_mb=0, disk_mb=0, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = ["prompt", "model", "operation", "duration"]
    side_effects = []
    user_visible_verification = []

    def get_status(self) -> ToolStatus:
        """Always UNAVAILABLE — credentials are not the problem.

        Deliberately ignores HIGGSFIELD_API_KEY / HIGGSFIELD_API_SECRET.
        Returning AVAILABLE because keys exist is what made this a trap:
        `video_selector` ranked it first for cinematic briefs and only
        discovered the 401 after it had committed to the provider. UNAVAILABLE
        drops it from `video_selector._select_best_tool` and from
        `tool_registry.find_fallback`.
        """
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """What this would really cost, per second, if the wrapper worked.

        The old table was per *clip* and quoted $0.80 for a 5 s Seedance clip.
        The rates below came from `POST api.higgsfield.ai/estimate/<endpoint_id>`
        on 2026-10-27 — free, authenticated, and the only safe way to price a
        model. Seedance 2.5 at 1080p is $1.1372 per second, so that same 5 s
        clip is $5.69 and a 30 s scene is $34: the old table was ~7x low, in the
        direction that costs money. Quoted rates are the 16:9 figure; vertical
        9:16 bills more per second, so treat these as a floor.

        An unlisted model falls back to the dearest known rate, never a cheap
        guess — under-quoting is the failure mode that matters here.
        """
        model = inputs.get("model", _DEFAULT_MODEL)
        duration = int(inputs.get("duration", "5"))
        usd_per_second = {
            "seedance_2.0": 1.1372,       # bytedance/seedance-2.5/*, 1080p
            "seedance_2.0_fast": 0.4622,  # same family at 720p
            "kling_3.0": 0.0840,          # kling-video/o3/image-reference, $0.420 / 5 s
            "wan_2.5": 0.0840,
        }
        rate = usd_per_second.get(model, max(usd_per_second.values()))
        return round(rate * duration, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Zero — `execute()` refuses immediately instead of polling for six minutes."""
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        """Refuse, without touching the network.

        The previous body built a payload, POSTed it to
        platform.higgsfield.ai/v1/generations and polled for six minutes. With
        the project's real key that request returns
        `401 {"detail":"Invalid credentials"}` every time, because the live API
        wants a single `Authorization: Key <key_id>:<secret>` header on
        api.higgsfield.ai/<endpoint_id>. Failing here, with the replacement
        route named, beats spending six minutes to arrive at the same answer.
        """
        return ToolResult(
            success=False,
            error=_RETIRED,
            data={
                "provider": "higgsfield",
                "retired": True,
                "replacement_tools": list(self.fallback_tools),
                "quoted_cost_usd": self.estimate_cost(inputs),
            },
            duration_seconds=0.0,
        )
