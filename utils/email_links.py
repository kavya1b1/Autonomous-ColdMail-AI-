"""Deterministic sanitization of profile links in generated email bodies.

The LLM prompt alone is not a reliable enough guarantee that a generated email
contains exactly the user's LinkedIn / GitHub / Portfolio links (and nothing
else — no LeetCode, no GeeksForGeeks, no duplicates, no invented URLs). This
module post-processes the email body deterministically, using the user's
saved profile as the single source of truth:

  1. Strip every existing http(s) URL out of the body (and any now-empty
     "Label: " lines left behind).
  2. Append a canonical three-line footer with exactly the profile's
     LinkedIn / GitHub / Portfolio links, in that order, each exactly once —
     omitting any that the profile doesn't have (never inventing one).

This is intentionally aggressive: it is safer to remove all links and then
re-add only the canonical three than to try to pattern-match and fix
individual bad links inline.
"""
import re
from typing import Optional

URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]\"']+", re.IGNORECASE)

# A line that, once its URL is stripped, is left as just a bare "Label:"
# with nothing after it (any label — not just known ones) is dead weight.
_BARE_LABEL_LINE = re.compile(r"^\s*[-•*]?\s*[A-Za-z][A-Za-z0-9 ]{0,30}:\s*$")


# A short, punctuation-free leftover (e.g. "LinkedIn", "Portfolio -", "Link")
# left on a line that originally contained a URL — dead label, no sentence.
_SHORT_LEFTOVER = re.compile(r"^[A-Za-z][A-Za-z ]{0,24}[:\-–]?$")


def _strip_all_urls(body: str) -> str:
    """Remove every URL from the body, then clean up now-empty label lines."""
    cleaned_lines = []
    for line in (body or "").split("\n"):
        had_url = bool(URL_PATTERN.search(line))
        line_no_url = URL_PATTERN.sub("", line)
        stripped = line_no_url.strip()
        if had_url and (not stripped or _SHORT_LEFTOVER.match(stripped)):
            # The whole line was (effectively) just a URL / label + URL — drop it.
            continue
        if not had_url and _BARE_LABEL_LINE.match(line_no_url):
            continue
        if had_url:
            # Inline URL removed mid-sentence: collapse the double space it leaves behind.
            line_no_url = re.sub(r" {2,}", " ", line_no_url).rstrip()
            line_no_url = re.sub(r"\s+([.,;:])", r"\1", line_no_url)
        cleaned_lines.append(line_no_url.rstrip())
    # Collapse 3+ consecutive blank lines down to at most 2 (one blank paragraph break).
    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def normalize_email_links(
    body: str,
    linkedin: Optional[str] = None,
    github: Optional[str] = None,
    portfolio: Optional[str] = None,
) -> str:
    """Return `body` with all links removed and the canonical footer re-appended.

    Only LinkedIn / GitHub / Portfolio are ever included, each at most once,
    sourced only from the arguments passed in (the user's saved profile) —
    never invented, never pulled from LeetCode/GFG/resume/LLM output.
    """
    cleaned = _strip_all_urls(body)

    footer_lines = []
    if linkedin and str(linkedin).strip():
        footer_lines.append(f"LinkedIn: {str(linkedin).strip()}")
    if github and str(github).strip():
        footer_lines.append(f"GitHub: {str(github).strip()}")
    if portfolio and str(portfolio).strip():
        footer_lines.append(f"Portfolio: {str(portfolio).strip()}")

    if not footer_lines:
        return cleaned

    return f"{cleaned}\n\n" + "\n".join(footer_lines)


def normalize_email_links_from_profile(body: str, profile) -> str:
    """Convenience wrapper accepting a UserProfile (or any object/dict with
    linkedin/github/portfolio attributes or keys)."""
    if isinstance(profile, dict):
        linkedin = profile.get("linkedin")
        github = profile.get("github")
        portfolio = profile.get("portfolio")
    else:
        linkedin = getattr(profile, "linkedin", None)
        github = getattr(profile, "github", None)
        portfolio = getattr(profile, "portfolio", None)
    return normalize_email_links(body, linkedin, github, portfolio)
