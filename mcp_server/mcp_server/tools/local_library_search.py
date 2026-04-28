"""Local Component Library Search.

Provides fuzzy search capabilities for the user's local .skp component library.
Components are indexed in the package assets/library.json manifest.
"""

import json
import re
from pathlib import Path
from typing import Optional

# Library index path
LIBRARY_PATH = Path(__file__).parent.parent / "assets" / "library.json"


def component_search_terms(component: dict) -> list[str]:
    """Return searchable names, aliases, and tags for a component."""
    terms: list[str] = []
    for key in ("id", "name", "name_en", "subcategory", "category"):
        value = component.get(key)
        if isinstance(value, str) and value:
            terms.append(value)

    aliases = component.get("aliases", {})
    if isinstance(aliases, dict):
        for values in aliases.values():
            if isinstance(values, list):
                terms.extend(str(value) for value in values if value)

    localized_names = component.get("localized_names", {})
    if isinstance(localized_names, dict):
        terms.extend(str(value) for value in localized_names.values() if value)

    for key in ("tags", "style_tags"):
        values = component.get(key, [])
        if isinstance(values, list):
            terms.extend(str(value) for value in values if value)

    return terms


def load_library() -> dict:
    """Load component library index.

    Returns:
        Library data dict or empty dict if not found.
    """
    if not LIBRARY_PATH.exists():
        return {"components": []}

    try:
        with open(LIBRARY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"components": []}


def fuzzy_match(query: str, text: str, threshold: float = 0.3) -> tuple[bool, float]:
    """Check if query fuzzy-matches text.

    Args:
        query: Search query (lowercase)
        text: Text to search in (lowercase)
        threshold: Match threshold (0.0-1.0), lower is more permissive

    Returns:
        (is_match, score) tuple
    """
    if not query or not text:
        return False, 0.0

    query_lower = query.lower()
    text_lower = text.lower()

    # Exact substring match
    if query_lower in text_lower:
        return True, 1.0

    # Word-level matching
    query_words = query_lower.split()
    text_words = text_lower.split()

    matched_words = sum(1 for qw in query_words if any(qw in tw for tw in text_words))
    if matched_words > 0:
        score = matched_words / len(query_words)
        return score >= threshold, score

    # Character n-gram matching (for typos)
    query_chunks = [query_lower[i:i+2] for i in range(len(query_lower) - 1)]
    if len(query_chunks) == 0:
        return False, 0.0

    text_chunks = set(text_lower[i:i+2] for i in range(len(text_lower) - 1))
    matches = sum(1 for chunk in query_chunks if chunk in text_chunks)
    score = matches / len(query_chunks)

    return score >= threshold, score


def search_library(
    query: str,
    category: Optional[str] = None,
    limit: int = 10,
    library_data: Optional[dict] = None
) -> list[dict]:
    """Search component library with fuzzy matching.

    Args:
        query: Search query (e.g., "sofa", "dining table")
        category: Optional category filter (furniture, fixtures, lighting)
        limit: Maximum number of results to return
        library_data: Optional pre-loaded library data

    Returns:
        List of matching components sorted by relevance score.
    """
    if library_data is None:
        library_data = load_library()

    components = library_data.get("components", [])
    if not components:
        return []

    query_lower = query.lower().strip()
    results = []

    for comp in components:
        # Filter by category if specified
        if category and comp.get("category") != category:
            continue

        # Calculate match score across names, aliases, and tags.
        best_score = 0.0
        for term in component_search_terms(comp):
            _, score = fuzzy_match(query_lower, term)
            best_score = max(best_score, score)

        # Include partial matches
        if best_score > 0:
            comp_result = comp.copy()
            comp_result["_match_score"] = round(best_score, 3)
            results.append(comp_result)

    # Sort by score descending
    results.sort(key=lambda x: x["_match_score"], reverse=True)

    return results[:limit]


def get_categories(library_data: Optional[dict] = None) -> list[str]:
    """Get list of available categories in the library.

    Returns:
        List of category names.
    """
    if library_data is None:
        library_data = load_library()

    categories = set()
    for comp in library_data.get("components", []):
        if "category" in comp:
            categories.add(comp["category"])

    return sorted(list(categories))


def get_components_by_category(
    category: str,
    library_data: Optional[dict] = None
) -> list[dict]:
    """Get all components in a specific category.

    Args:
        category: Category name
        library_data: Optional pre-loaded library data

    Returns:
        List of components in the category.
    """
    if library_data is None:
        library_data = load_library()

    return [
        comp for comp in library_data.get("components", [])
        if comp.get("category") == category
    ]


def format_search_results(results: list[dict], include_score: bool = True) -> str:
    """Format search results for display to user.

    Args:
        results: List of component dicts
        include_score: Whether to include match score

    Returns:
        Formatted string for user display.
    """
    if not results:
        return "No matching components found."

    lines = []
    for i, comp in enumerate(results, 1):
        name = comp.get("name", "Unknown")
        aliases = comp.get("aliases", {})
        localized = aliases.get("zh-CN", []) if isinstance(aliases, dict) else []
        localized_name = localized[0] if localized else comp.get("name_en", "")
        category = comp.get("category", "uncategorized")

        line = f"{i}. {name}"
        if localized_name:
            line += f" ({localized_name})"
        line += f" - {category}"

        if include_score and "_match_score" in comp:
            line += f" [score: {comp['_match_score']}]"

        lines.append(line)

    return "\n".join(lines)


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python local_library_search.py <query>")
        sys.exit(1)

    query = sys.argv[1]
    category = sys.argv[2] if len(sys.argv) > 2 else None

    results = search_library(query, category=category)
    print(f"Search for '{query}'{f' in category {category}' if category else ''}:\n")
    print(format_search_results(results))
