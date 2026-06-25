"""PoC3 entity/relation extractor: chunk text -> Claude -> KG triplets.

Uses LlamaIndex SchemaLLMPathExtractor with an OPEN schema (strict=False).
The entity/relation lists below are HINTS that bias Claude toward the
equipment-maintenance domain and suppress hallucination, but extraction is
NOT limited to them. Goal (PoC3): connect one document end-to-end, not
exhaustive relation coverage — under-extraction is the usual trap, so keep
hints loose and accept a few solid relations.
"""
from __future__ import annotations

from typing import Any, Literal

from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from llama_index.llms.anthropic import Anthropic as _Anthropic

from app.core.config import settings


class Anthropic(_Anthropic):
    """Anthropic LLM with a fix for the structured-extraction tool_choice bug.

    llama-index-core 0.14.x forwards ``tool_choice=None`` (its default for
    structured_predict) through **kwargs into ``_prepare_chat_with_tools``,
    where it is spread *after* the correctly-built Anthropic tool_choice object
    and overrides it with null. The Anthropic API then rejects the request:
    ``400 tool_choice: Input should be an object``.

    Drop any non-dict tool_choice from kwargs so the parent's computed object
    (type="any"/"auto") survives. A caller-supplied dict is still respected.
    """

    def _prepare_chat_with_tools(self, *args: Any, **kwargs: Any) -> dict:
        if not isinstance(kwargs.get("tool_choice"), dict):
            kwargs.pop("tool_choice", None)
        return super()._prepare_chat_with_tools(*args, **kwargs)

# --- domain schema hints (equipment maintenance manual) ---
Entities = Literal[
    "설비", "펌프", "모터", "베어링", "기계식실", "열교환기",
    "구성요소", "점검주기", "담당팀", "절차",
]
Relations = Literal[
    "구동", "지지", "연결", "구성", "정지", "점검", "담당", "교체", "주기",
]
# soft validation schema (used as a hint; strict=False keeps it non-binding):
# which relations may plausibly leave each entity type.
VALIDATION_SCHEMA: dict[str, list[str]] = {
    "펌프": ["구동", "지지", "연결", "구성"],
    "모터": ["정지", "점검", "담당", "주기"],
    "베어링": ["점검", "교체", "담당", "주기"],
    "기계식실": ["점검", "담당", "주기"],
    "설비": ["구동", "지지", "연결", "구성", "정지", "점검"],
    "절차": ["정지", "점검", "교체"],
}


def build_llm() -> Anthropic:
    """Claude client from settings; fail loudly if the key is still a placeholder."""
    key = settings.anthropic_api_key
    if not key or key.startswith("sk-xxx") or key == "":
        raise RuntimeError(
            "ANTHROPIC_API_KEY missing/placeholder — set a real key in backend/.env "
            "before running PoC3."
        )
    return Anthropic(
        model=settings.anthropic_model,
        api_key=key,
        max_tokens=2048,
    )


def build_extractor(
    llm: Anthropic | None = None,
    max_triplets_per_chunk: int = 12,
) -> SchemaLLMPathExtractor:
    """Open-schema path extractor biased by the domain hints above."""
    return SchemaLLMPathExtractor(
        llm=llm or build_llm(),
        possible_entities=Entities,        # hint, not a hard limit (strict=False)
        possible_relations=Relations,      # hint, not a hard limit
        kg_validation_schema=VALIDATION_SCHEMA,
        strict=False,                      # OPEN schema -> suppress, don't block
        max_triplets_per_chunk=max_triplets_per_chunk,
        num_workers=1,                     # Windows: avoid mp spawn / rate spikes
    )
