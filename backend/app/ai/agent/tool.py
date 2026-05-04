"""@tool decorator — auto-generates JSON Schema from type hints + docstrings.

Usage::

    from app.ai.agent import tool, RunContext

    @tool
    def search_files(ctx: RunContext[MyDeps], query: str, max_results: int = 5) -> str:
        \"\"\"Search files matching a query.

        Args:
            query: The search query string.
            max_results: Maximum number of results to return.
        \"\"\"
        ...

The decorator inspects the function signature and docstring to produce a
``ToolDef`` (JSON Schema) automatically.  If the first parameter is typed
``RunContext[T]``, it is injected at call time and hidden from the schema.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, get_args, get_origin

from app.ai.agent.context import RunContext
from app.ai.agent.model import ToolDef

# Python type → JSON Schema type mapping
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _json_schema_type(annotation: Any) -> dict[str, Any]:
    """Convert a Python type annotation to a JSON Schema fragment."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {"type": "string"}

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Optional[X] → nullable X
    if origin is type(None):
        return {"type": "string"}

    # list[X]
    if origin is list:
        item_schema = _json_schema_type(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item_schema}

    # dict[str, X]
    if origin is dict:
        val_schema = _json_schema_type(args[1]) if len(args) > 1 else {}
        return {"type": "object", "additionalProperties": val_schema}

    # Union / Optional
    if origin is type(None):
        return {"type": "string"}

    # Plain types
    if annotation in _TYPE_MAP:
        return {"type": _TYPE_MAP[annotation]}

    # Enum types
    if isinstance(annotation, type) and issubclass(annotation, __import__("enum").Enum):
        return {
            "type": "string",
            "enum": [e.value for e in annotation],
        }

    return {"type": "string"}


def _parse_docstring_args(docstring: str | None) -> dict[str, str]:
    """Parse Google-style ``Args:`` section from a docstring.

    Returns a mapping of parameter name → description.
    """
    if not docstring:
        return {}

    descriptions: dict[str, str] = {}
    in_args = False
    current_name: str | None = None
    current_lines: list[str] = []

    for line in docstring.splitlines():
        stripped = line.strip()

        if stripped.lower().startswith("args:"):
            in_args = True
            continue

        if in_args:
            # New section header (Returns:, Raises:, etc.) ends Args block
            if (
                stripped
                and not stripped[0].isspace()
                and stripped.endswith(":")
                and ":" not in stripped[:-1]
            ):
                # Save last param
                if current_name:
                    descriptions[current_name] = " ".join(current_lines).strip()
                break

            # New parameter line: "  param_name: description" or "  param_name (type): description"
            match = re.match(r"^\s{2,}(\w+)\s*(?:\([^)]*\))?\s*:\s*(.*)", line)
            if match:
                if current_name:
                    descriptions[current_name] = " ".join(current_lines).strip()
                current_name = match.group(1)
                current_lines = [match.group(2)] if match.group(2) else []
            elif current_name and stripped:
                # Continuation line
                current_lines.append(stripped)

    # Save last param
    if current_name and current_name not in descriptions:
        descriptions[current_name] = " ".join(current_lines).strip()

    return descriptions


def _is_run_context(annotation: Any) -> bool:
    """Check if an annotation is RunContext or RunContext[T].

    Handles both live type objects and stringified annotations
    (from ``from __future__ import annotations``).
    """
    if annotation is RunContext:
        return True
    origin = get_origin(annotation)
    if origin is RunContext:
        return True
    # Stringified annotations: "RunContext[...]" or "RunContext"
    if isinstance(annotation, str):
        stripped = annotation.strip()
        return stripped == "RunContext" or stripped.startswith("RunContext[")
    return False


@dataclass
class Tool:
    """A registered tool: the function + its auto-generated schema."""

    name: str
    description: str
    func: Callable[..., Any]
    takes_ctx: bool
    tool_def: ToolDef
    is_async: bool = field(default=False)

    async def execute(self, ctx: RunContext[Any] | None, args: dict[str, Any]) -> str:
        """Execute the tool function, injecting context if needed.

        Supports both sync and async tool functions.
        Returns a JSON string.
        """
        if self.takes_ctx:
            if ctx is None:
                raise RuntimeError(
                    f"Tool {self.name!r} requires RunContext but none provided"
                )
            if self.is_async:
                result = await self.func(ctx, **args)
            else:
                result = await asyncio.to_thread(self.func, ctx, **args)
        else:
            if self.is_async:
                result = await self.func(**args)
            else:
                result = await asyncio.to_thread(self.func, **args)

        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)


def tool(
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> Tool | Callable[[Callable[..., Any]], Tool]:
    """Decorator that turns a function into a ``Tool`` with auto-generated schema.

    Can be used bare (``@tool``) or with arguments (``@tool(name="custom")``).

    Args:
        name:        Override the tool name (default: function name).
        description: Override the tool description (default: first docstring line).
        parameters:  Override the auto-generated JSON Schema for tool parameters.
                     Use this to provide a hand-crafted schema when the auto-
                     generated schema is too weak (e.g. for complex nested types).
    """

    def _wrap(fn: Callable[..., Any]) -> Tool:
        tool_name = name or fn.__name__
        sig = inspect.signature(fn)
        docstring = inspect.getdoc(fn) or ""

        # Extract first line of docstring as description
        tool_desc = (
            description or docstring.split("\n")[0].strip() or f"Tool: {tool_name}"
        )

        # Parse parameter descriptions from docstring
        param_docs = _parse_docstring_args(docstring)

        # Resolve stringified annotations (from `from __future__ import annotations`)
        try:
            from typing import get_type_hints

            hints = get_type_hints(fn, include_extras=True)
        except Exception:  # noqa: BLE001
            hints = {}

        # Build JSON Schema from parameters
        properties: dict[str, Any] = {}
        required: list[str] = []
        takes_context = False

        for i, (param_name, param) in enumerate(sig.parameters.items()):
            # Prefer resolved hint; fall back to raw annotation
            annotation = hints.get(param_name, param.annotation)

            # First param: check if it's RunContext
            if i == 0 and _is_run_context(annotation):
                takes_context = True
                continue

            schema = _json_schema_type(annotation)
            if param_name in param_docs:
                schema["description"] = param_docs[param_name]

            properties[param_name] = schema
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        if parameters is not None:
            # Caller-provided schema overrides auto-generated one
            parameters_schema = parameters
        else:
            parameters_schema = {
                "type": "object",
                "properties": properties,
            }
            if required:
                parameters_schema["required"] = required

        td = ToolDef(
            name=tool_name,
            description=tool_desc,
            parameters=parameters_schema,
        )

        is_async_fn = inspect.iscoroutinefunction(fn)

        return Tool(
            name=tool_name,
            description=tool_desc,
            func=fn,
            takes_ctx=takes_context,
            tool_def=td,
            is_async=is_async_fn,
        )

    if func is not None:
        # @tool  (no parentheses)
        return _wrap(func)

    # @tool(name=..., description=...)
    return _wrap


# Convenience: maximum tool output length before truncation
MAX_TOOL_OUTPUT_CHARS = 12_000


def scrub_tool_output(text: str, max_chars: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Truncate tool output to avoid blowing up context windows."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 80] + "\n...[truncated]..."
