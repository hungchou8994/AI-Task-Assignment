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
    use_vertexai = settings.gemini_vertexai or settings.google_genai_use_vertexai
    if use_vertexai:
        if settings.gemini_vertex_use_api_key:
            if not settings.gemini_api_key:
                raise ValueError("GEMINI_API_KEY not configured")
            client = genai.Client(vertexai=True, api_key=settings.gemini_api_key)
        else:
            project = settings.gemini_vertex_project or settings.google_cloud_project
            location = (
                settings.gemini_vertex_location
                or settings.google_cloud_location
                or "us-central1"
            )
            if not project:
                raise ValueError(
                    "Vertex AI Gemini requires GEMINI_VERTEX_PROJECT or GOOGLE_CLOUD_PROJECT"
                )
            client = genai.Client(vertexai=True, project=project, location=location)
    else:
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
