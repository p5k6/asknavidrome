import logging
import re
import unicodedata
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)


def normalize_string(s: str) -> str:
    """Normalize a string for comparison purposes.

    Handles case, punctuation, unicode, and common variations.
    Does not modify the original string for display.
    """
    if not s:
        return ""

    s = s.lower().strip()

    s = unicodedata.normalize('NFKD', s)
    s = s.encode('ascii', 'ignore').decode('ascii')

    s = re.sub(r"[.'´`'-]+", "", s)

    s = re.sub(r"[^\w\s]", "", s)

    s = re.sub(r"^\s*the\s+", "", s)

    s = re.sub(r"\s+", "", s)

    return s


def songs_match(title_query: str, title_result: str, artist_query: Optional[str] = None, artist_result: Optional[str] = None) -> Tuple[bool, int]:
    """Determine if a song matches the query and return a match score.

    Returns (matches, score) where:
    - matches=True if this could be the right song
    - score is a ranking (higher is better):
      - 1000: exact title + exact artist
      - 800: exact title only
      - 600: title contains query as complete phrase
      - 400: title starts with query
      - 200: query in title
      - 0: no match
    """
    query_norm = normalize_string(title_query)
    result_norm = normalize_string(title_result)

    if query_norm == result_norm:
        score = 800
        if artist_query and artist_result and artists_match(artist_query, artist_result):
            score = 1000
        return True, score

    if query_norm in result_norm:
        if result_norm.startswith(query_norm):
            return True, 400
        return True, 200

    return False, 0


def artists_match(artist_query: str, artist_result: str) -> bool:
    """Check if two artist names match (ignoring case, punctuation, unicode)."""
    return normalize_string(artist_query) == normalize_string(artist_result)


def find_best_artist(query: str, artists: List[Dict]) -> Optional[Dict]:
    """Find the best matching artist from a list of search results.

    Prefers exact normalized matches. Returns None if no good match found.
    """
    if not artists:
        return None

    query_norm = normalize_string(query)

    for artist in artists:
        name = artist.get('name', '')
        if normalize_string(name) == query_norm:
            logger.debug(f"Found exact normalized match for artist: {query} -> {name}")
            return artist

    logger.warning(f"No exact artist match found for {query}, artists available: {[a.get('name') for a in artists[:3]]}")
    return artists[0]


def find_best_song(query: str, songs: List[Dict], artist_filter: Optional[str] = None) -> Optional[Dict]:
    """Find the best matching song from a list of search results.

    If artist_filter is provided, strongly prefers songs matching that artist.
    Returns None if no good match found.
    """
    if not songs:
        return None

    candidates = []
    for song in songs:
        title = song.get('title', '')
        artist = song.get('artist', '')

        matches, score = songs_match(query, title, artist_filter, artist)
        if matches:
            candidates.append((score, song))
            if score >= 800:
                logger.debug(f"  HIGH MATCH: '{title}' by '{artist}' (score: {score})")

    if not candidates:
        logger.warning(f"No song match found for query='{query}' with artist_filter='{artist_filter}'")
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_song = candidates[0]

    logger.info(f"Found song match for {query}: {best_song.get('title')} by {best_song.get('artist')} (score: {best_score})")

    return best_song


def find_song_by_exact_title(query: str, songs: List[Dict]) -> Optional[List[Dict]]:
    """Find all songs with exact normalized title match.

    Useful for finding exact title matches when disambiguating.
    """
    query_norm = normalize_string(query)
    matches = []

    for song in songs:
        title = song.get('title', '')
        if normalize_string(title) == query_norm:
            matches.append(song)

    return matches if matches else None


def deep_search(connection, search_func, term: str, max_results: int = 500) -> List[Dict]:
    """Perform a deep search using pagination to get more results than the default 20.

    The libsonic library's search3 method has page limits. This attempts to get
    more results by doing multiple searches with different query variations.

    Args:
        connection: SubsonicConnection object
        search_func: Method to call (e.g., connection.search_song)
        term: Search term
        max_results: Maximum results to attempt to retrieve

    Returns:
        List of search results, up to max_results items
    """
    results = []
    seen_ids = set()

    # First try a direct search
    initial = search_func(term)
    if initial:
        for item in initial:
            item_id = item.get('id')
            if item_id not in seen_ids:
                results.append(item)
                seen_ids.add(item_id)

    return results
