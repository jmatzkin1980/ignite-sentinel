from __future__ import annotations

from pathlib import Path

from .core.markdown import parse_frontmatter
from .technique_registry import normalize_respondent_profile

DOMAIN_CONTEXT_FOLDERS = {
    "business": "00_raw/01_business_context",
    "technical": "00_raw/02_technology_context",
    "design": "00_raw/03_design_context",
    "quality": "00_raw/04_quality_context",
    "interactions": "00_raw/05_interactions",
}
DOMAIN_CONTEXT_PATTERNS = ("*.md", "*.txt", "*.html", "*.htm")


def respondent_profile_from_domain_context(base: Path) -> str | None:
    """Return only an explicitly declared respondent profile from domain context.

    Supported declaration is frontmatter such as
    ``respondent_profile: technical`` or ``respondent_profile: business``.
    Free text, domain folder names, roles, and titles are intentionally ignored.
    """
    for folder in DOMAIN_CONTEXT_FOLDERS.values():
        root = base / folder
        if not root.exists():
            continue
        for pattern in DOMAIN_CONTEXT_PATTERNS:
            for path in sorted(root.rglob(pattern)):
                profile = profile_from_context_file(path)
                if profile:
                    return profile
    return None


def profile_from_context_file(path: Path) -> str | None:
    frontmatter = parse_frontmatter(path.read_text(encoding="utf-8"))
    raw = frontmatter.get("respondent_profile") if isinstance(frontmatter, dict) else None
    return normalize_respondent_profile(str(raw)) if raw is not None else None
