"""
Anthropic Claude client wrapper.

Structured output uses a single forced tool call: the schema is passed as a tool
and `tool_choice` pins Claude to it, so the response is always that tool's input
object. This mirrors the previous function-calling implementation exactly, which
is why all nine agents work unmodified.

Native structured outputs (`output_config.format`) was the first choice but caps
a schema at 24 optional parameters; the full-profile extraction schema has 28,
because extraction deliberately marks nearly every field optional so absent
sections are omitted rather than invented. Forced tool use has no such limit and
preserves that omit-when-absent behaviour.

Adaptive thinking is left on — Claude decides per request how much to reason,
which is what drives the quality gain over the previous provider.
"""
import logging
from typing import Any

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

_async_client: anthropic.AsyncAnthropic | None = None

# `max_tokens` bounds thinking + visible output together. Agent call sites were
# sized for a no-thinking model, so we floor the budget to leave thinking room
# rather than truncating mid-answer. Callers asking for more than this keep it.
_MIN_TOKEN_BUDGET = 16_000


# Current-generation models that support adaptive thinking and the `effort`
# parameter, both of which this client sends on every call. Notably excludes
# Haiku 4.5, which supports neither. A request naming anything else — e.g. a
# stale "gpt-4o-mini" from a cached frontend bundle — falls back to the
# configured default instead of failing the whole generation.
# Keep in sync with MODELS in frontend/components/ModelSelectorModal.tsx.
SUPPORTED_MODELS = frozenset({
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-opus-4-8",
    "claude-fable-5",
})


def _resolve_model(model: str | None) -> str:
    if not model:
        return settings.anthropic_model
    if model in SUPPORTED_MODELS:
        return model
    logger.warning(
        "Unsupported model %r requested; falling back to %s. Supported: %s",
        model, settings.anthropic_model, ", ".join(sorted(SUPPORTED_MODELS)),
    )
    return settings.anthropic_model


def get_async_client() -> anthropic.AsyncAnthropic:
    global _async_client
    if _async_client is None:
        _async_client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            # Opus is capacity-constrained at peak; the SDK retries 429/5xx/529
            # with exponential backoff.
            max_retries=settings.anthropic_max_retries,
            timeout=settings.anthropic_timeout_seconds,
        )
    return _async_client


def _build_system(system_prompt: str, use_cache: bool) -> Any:
    """
    Agent system prompts are large and byte-stable across requests, so caching
    them turns most of the input cost into cache reads. Prompts under the model's
    minimum cacheable prefix simply won't cache — that is not an error.
    """
    if not use_cache:
        return system_prompt
    return [{
        "type": "text",
        "text": system_prompt,
        "cache_control": {"type": "ephemeral"},
    }]


def _first_text(response: Any) -> str:
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def _first_tool_input(response: Any) -> dict[str, Any] | None:
    for block in response.content:
        if block.type == "tool_use":
            return dict(block.input)
    return None


def _guard_stop_reason(response: Any, label: str) -> None:
    """Check stop_reason before trusting content — a refusal has no usable body."""
    if response.stop_reason == "refusal":
        detail = getattr(response, "stop_details", None)
        category = getattr(detail, "category", None) if detail else None
        raise ValueError(
            f"Claude declined the '{label}' request"
            + (f" (category: {category})" if category else "")
            + ". Check the input text for content that trips safety classifiers."
        )
    if response.stop_reason == "max_tokens":
        raise ValueError(
            f"Claude hit the token ceiling on '{label}' before finishing. "
            "Raise max_tokens for this call."
        )


async def call_claude_structured(
    system_prompt: str,
    user_message: str,
    tool_name: str,
    tool_description: str,
    output_schema: dict,
    model: str | None = None,
    max_tokens: int = 4096,
    use_cache: bool = True,
    effort: str | None = None,
) -> dict[str, Any]:
    """
    Call Claude and return structured JSON matching `output_schema`.

    Implemented as a single forced tool call, so the return value is the tool's
    input object — already parsed by the SDK, with absent optional fields simply
    omitted rather than filled with empty values.
    """
    client = get_async_client()
    effective_model = _resolve_model(model)

    tools = [{
        "name": tool_name,
        "description": tool_description,
        "input_schema": output_schema,
    }]

    kwargs: dict[str, Any] = {}
    chosen_effort = effort or settings.anthropic_effort
    if chosen_effort:
        kwargs["output_config"] = {"effort": chosen_effort}

    try:
        response = await client.messages.create(
            model=effective_model,
            max_tokens=max(max_tokens, _MIN_TOKEN_BUDGET),
            thinking={"type": "adaptive"},
            system=_build_system(system_prompt, use_cache),
            messages=[{"role": "user", "content": user_message}],
            tools=tools,
            tool_choice={"type": "tool", "name": tool_name},
            **kwargs,
        )
    except anthropic.APIStatusError as e:
        logger.error("Anthropic API error (%s) on '%s': %s", e.status_code, tool_name, e)
        raise
    except anthropic.APIConnectionError as e:
        logger.error("Anthropic connection error on '%s': %s", tool_name, e)
        raise

    _guard_stop_reason(response, tool_name)

    logger.debug(
        "%s [%s]: in=%d cache_read=%d out=%d",
        tool_name,
        effective_model,
        response.usage.input_tokens,
        getattr(response.usage, "cache_read_input_tokens", 0) or 0,
        response.usage.output_tokens,
    )

    result = _first_tool_input(response)
    if result is None:
        raise ValueError(
            f"Claude did not return a tool call for '{tool_name}' "
            f"(stop_reason={response.stop_reason})"
        )
    return result


async def call_claude_text(
    system_prompt: str,
    user_message: str,
    model: str | None = None,
    max_tokens: int = 2048,
    use_cache: bool = True,
) -> str:
    """Plain text response from Claude. Signature-compatible with the original."""
    client = get_async_client()
    effective_model = _resolve_model(model)

    response = await client.messages.create(
        model=effective_model,
        max_tokens=max(max_tokens, _MIN_TOKEN_BUDGET),
        thinking={"type": "adaptive"},
        system=_build_system(system_prompt, use_cache),
        messages=[{"role": "user", "content": user_message}],
    )

    _guard_stop_reason(response, "text_completion")
    return _first_text(response)
