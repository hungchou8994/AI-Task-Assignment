"""app.ai.gemini_client — Pydantic models and Gemini API wrapper.

Exports: ExtractedTask, ExtractionResult, call_gemini

No imports from other app.ai.* modules.
"""

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from app.config import get_settings


class Recommendation(BaseModel):
    rank: int = Field(ge=1, le=3)
    person_id: Optional[str] = None
    name: str
    confidence_score: float = Field(ge=0, le=1)
    reasoning: str


class ExtractedTask(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Literal["low", "medium", "high"]
    due_date: Optional[str] = None
    confidence_score: float = Field(default=0.5, ge=0, le=1)
    assignee_recommendations: list[Recommendation] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    source_summary: str
    tasks: list[ExtractedTask]


def call_gemini(
    user_prompt: Union[str, list[types.Part]],
    system_prompt: str,
) -> ExtractionResult:
    """Call Gemini with structured output schema enforcement.

    user_prompt: plain string (text/url mode) OR list[Part] (email mode with attachments).
    The google-genai SDK's generate_content() contents parameter accepts both natively.

    Raises ValueError if GEMINI_API_KEY is not set or Gemini returns invalid schema.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY not configured")
    client = genai.Client(api_key=settings.gemini_api_key)
    resp = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_prompt,  # type: ignore[arg-type]  # SDK accepts str|list[Part] at runtime
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=ExtractionResult,
            temperature=settings.gemini_temperature,
        ),
    )
    if resp.parsed is None:
        raise ValueError("Gemini returned invalid schema")
    return resp.parsed  # type: ignore[return-value]
