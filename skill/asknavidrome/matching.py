import logging
import re
import unicodedata
from difflib import SequenceMatcher
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

    s = s.replace('&', ' and ')

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
        if artist_query and artist_result and artist_credit_matches(artist_query, artist_result):
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


def strip_leading_article(term: str) -> str:
    """Remove a leading "the" from a search term.

    Alexa often hears "the Grateful Dead" while the library stores "Grateful Dead", and
    Navidrome's search does not ignore the article. Used for search terms only.
    """
    stripped = re.sub(r"^\s*the\s+", "", term or "", flags=re.IGNORECASE).strip()
    return stripped or (term or "")


_CREDIT_SPLIT = re.compile(r"\s+(?:feat\.?|ft\.?|featuring|with)\s+|\s*[,;/]\s*", re.IGNORECASE)


def artist_credit_matches(artist_query: str, credit: str) -> bool:
    """Check if an artist query matches a song's artist credit.

    Matches the whole credit, or any one name in a multi-artist credit such as
    "The Shins feat. Iron & Wine".
    """
    query_norm = normalize_string(artist_query)
    if not query_norm:
        return False

    if query_norm == normalize_string(credit):
        return True

    parts = _CREDIT_SPLIT.split(credit or "")
    return len(parts) > 1 and any(normalize_string(part) == query_norm for part in parts)


def artist_similarity(a: str, b: str) -> float:
    """Return how alike two artist names are, from 0.0 to 1.0, after normalizing."""
    return SequenceMatcher(None, normalize_string(a), normalize_string(b)).ratio()


def distinct_by_artist(songs: List[Dict]) -> List[Dict]:
    """Keep one song per distinct artist, in the original order.

    The same recording often appears on several releases. One copy per artist is
    enough to play it or to ask which artist is meant.
    """
    seen = set()
    result = []
    for song in songs:
        key = normalize_string(song.get('artist', ''))
        if key not in seen:
            seen.add(key)
            result.append(song)
    return result


def pick_song_by_similar_artist(artist_query: str, songs: List[Dict],
                                min_similarity: float = 0.75, margin: float = 0.15) -> Optional[Dict]:
    """Pick the song whose artist is clearly the closest to a misheard artist name.

    Only used on a short list of songs that already have the requested title. Returns
    None unless one artist is close enough and clearly ahead of the others.
    """
    scored = sorted(((artist_similarity(artist_query, s.get('artist', '')), s) for s in distinct_by_artist(songs)),
                    key=lambda pair: pair[0], reverse=True)
    if not scored:
        return None

    top_score, top_song = scored[0]
    if top_score < min_similarity:
        return None

    if len(scored) > 1 and top_score - scored[1][0] < margin:
        return None

    logger.debug(f"Artist '{artist_query}' is closest to '{top_song.get('artist')}' (similarity: {top_score:.2f})")
    return top_song


def split_song_and_artist(phrase: str) -> List[Tuple[str, str]]:
    """Split "<song> by <artist>" into (song, artist) pairs, rightmost "by" first.

    Alexa sometimes puts the whole phrase in the song slot. Song titles can contain
    "by", so every split is returned and the caller checks each one against the library.
    """
    parts = re.split(r"\s+by\s+", (phrase or "").strip(), flags=re.IGNORECASE)
    pairs = []
    for i in range(len(parts) - 1, 0, -1):
        song = " by ".join(parts[:i]).strip()
        artist = " by ".join(parts[i:]).strip()
        if song and artist:
            pairs.append((song, artist))
    return pairs


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


def find_best_song(query: str, songs: List[Dict], artist_filter: Optional[str] = None,
                   require_artist: bool = False) -> Optional[Dict]:
    """Find the best matching song from a list of search results.

    If artist_filter is provided, strongly prefers songs matching that artist. With
    require_artist, songs by any other artist are never returned.
    Returns None if no good match found.
    """
    if not songs:
        return None

    candidates = []
    for song in songs:
        title = song.get('title', '')
        artist = song.get('artist', '')

        matches, score = songs_match(query, title, artist_filter, artist)
        if matches and require_artist and not (artist_filter and artist_credit_matches(artist_filter, artist)):
            continue
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
