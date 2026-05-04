"""Skill loader — loads markdown instruction files with YAML frontmatter.

Skills are instruction bundles that get prepended to the agent's system prompt.
They live as ``.md`` files, optionally with YAML frontmatter for metadata.

Format::

    ---
    name: extraction_policy
    description: Policy for autonomous task extraction
    ---

    # Extraction Policy

    You are an autonomous agent that ...

Usage::

    from app.ai.agent.skills import load_skills

    text = load_skills(["extraction_policy"], skills_dir=Path("./skills"))
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# YAML frontmatter regex (between --- fences at the top of the file)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter, returning only the body."""
    return _FRONTMATTER_RE.sub("", text)


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse simple key: value pairs from YAML frontmatter (no nested structures)."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def load_skill_file(path: Path) -> str:
    """Load a single skill file and return its body (frontmatter stripped)."""
    content = path.read_text(encoding="utf-8")
    return _strip_frontmatter(content).strip()


def load_skills(
    skill_names: list[str],
    *,
    skills_dir: Path | None = None,
) -> str:
    """Load and concatenate multiple skills into a single instruction string.

    Each skill is looked up as ``{skills_dir}/{name}.md`` or
    ``{skills_dir}/{name}/SKILL.md``.

    Returns the concatenated skill bodies separated by ``\\n\\n---\\n\\n``.
    Missing skills emit a warning and are skipped.
    """
    if not skill_names:
        return ""

    sections: list[str] = []
    for name in skill_names:
        body = _resolve_skill(name, skills_dir)
        if body:
            sections.append(body)

    return "\n\n---\n\n".join(sections)


def _resolve_skill(name: str, skills_dir: Path | None) -> str | None:
    """Try multiple locations for a skill file."""
    if skills_dir is None:
        logger.warning("No skills_dir configured; cannot load skill %r", name)
        return None

    # Direct: skills_dir/name.md
    direct = skills_dir / f"{name}.md"
    if direct.is_file():
        logger.debug("Loaded skill %r from %s", name, direct)
        return load_skill_file(direct)

    # Nested: skills_dir/name/SKILL.md (OpenCode convention)
    nested = skills_dir / name / "SKILL.md"
    if nested.is_file():
        logger.debug("Loaded skill %r from %s", name, nested)
        return load_skill_file(nested)

    # Nested: skills_dir/name/index.md
    index = skills_dir / name / "index.md"
    if index.is_file():
        logger.debug("Loaded skill %r from %s", name, index)
        return load_skill_file(index)

    logger.warning("Skill %r not found in %s", name, skills_dir)
    return None


# ------------------------------------------------------------------ #
# Dynamic skill support                                               #
# ------------------------------------------------------------------ #

SkillSource = str | Path | Callable[[], str]
"""A skill can be a name (resolved from skills_dir), a Path, or a callable."""


def resolve_skill_sources(
    sources: list[SkillSource],
    *,
    skills_dir: Path | None = None,
) -> str:
    """Resolve a heterogeneous list of skill sources into a single string."""
    sections: list[str] = []

    for source in sources:
        if callable(source):
            sections.append(source())
        elif isinstance(source, Path):
            if source.is_file():
                sections.append(load_skill_file(source))
            else:
                logger.warning("Skill path does not exist: %s", source)
        elif isinstance(source, str):
            body = _resolve_skill(source, skills_dir)
            if body:
                sections.append(body)

    return "\n\n---\n\n".join(sections)
