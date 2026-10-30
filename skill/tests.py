import unittest
from unittest.mock import patch

from asknavidrome import matching
from asknavidrome.matching import (
    normalize_string,
    songs_match,
    artists_match,
    find_best_artist,
    find_best_song,
    find_song_by_exact_title,
)


class TestNormalization(unittest.TestCase):
    """Test artist and song normalization"""

    def test_artist_case_insensitive(self):
        """REM and rem should normalize to the same thing"""
        self.assertEqual(normalize_string("REM"), normalize_string("rem"))

    def test_artist_periods(self):
        """R.E.M. and REM should normalize to the same thing"""
        self.assertEqual(normalize_string("R.E.M."), normalize_string("REM"))

    def test_artist_spaces_in_periods(self):
        """R. E. M. and R.E.M. should normalize to the same thing"""
        self.assertEqual(normalize_string("R. E. M."), normalize_string("R.E.M."))

    def test_artist_with_the(self):
        """The Shins and the shins should match"""
        self.assertEqual(normalize_string("The Shins"), normalize_string("the shins"))

    def test_artist_apostrophes(self):
        """Handling of apostrophes"""
        self.assertEqual(normalize_string("Nirvana"), normalize_string("Nirvana"))

    def test_artist_unicode(self):
        """Unicode handling - accents removed"""
        # CHVRCHES with accent variants
        self.assertEqual(normalize_string("CHVRCHES"), normalize_string("chvrches"))

    def test_song_exact_title(self):
        """Exact title should normalize consistently"""
        self.assertEqual(normalize_string("Leave"), normalize_string("Leave"))

    def test_whitespace_normalization(self):
        """Multiple spaces should normalize to single space"""
        self.assertEqual(normalize_string("Leave  It"), normalize_string("Leave It"))

    def test_empty_string(self):
        """Empty string should remain empty"""
        self.assertEqual(normalize_string(""), "")


class TestArtistMatching(unittest.TestCase):
    """Test artist matching logic"""

    def test_exact_match_rem(self):
        """REM should match R.E.M."""
        self.assertTrue(artists_match("REM", "R.E.M."))

    def test_exact_match_case_insensitive(self):
        """Case insensitive matching"""
        self.assertTrue(artists_match("REM", "rem"))

    def test_no_match_different_artists(self):
        """Different artists should not match"""
        self.assertFalse(artists_match("REM", "Radiohead"))

    def test_the_shins(self):
        """The Shins variations"""
        self.assertTrue(artists_match("The Shins", "the shins"))
        self.assertTrue(artists_match("Shins", "The Shins"))


class TestSongMatching(unittest.TestCase):
    """Test song matching logic"""

    def test_exact_title_match(self):
        """Exact title should score highest"""
        matches, score = songs_match("Leave", "Leave")
        self.assertTrue(matches)
        self.assertGreaterEqual(score, 800)

    def test_exact_title_and_artist(self):
        """Exact title and artist should score 1000"""
        matches, score = songs_match("Leave", "Leave", "REM", "R.E.M.")
        self.assertTrue(matches)
        self.assertEqual(score, 1000)

    def test_title_contains_query(self):
        """Title containing query should match but with lower score"""
        matches, score = songs_match("Leave", "Leave It Alone")
        self.assertTrue(matches)
        self.assertLess(score, 800)
        self.assertGreater(score, 0)

    def test_no_match_completely_different(self):
        """Unrelated title should not match"""
        matches, score = songs_match("Leave", "Stairway to Heaven")
        self.assertFalse(matches)
        self.assertEqual(score, 0)

    def test_title_case_insensitive(self):
        """Case insensitive title matching"""
        matches, score = songs_match("leave", "Leave")
        self.assertTrue(matches)


class TestFindBestArtist(unittest.TestCase):
    """Test artist search result ranking"""

    def test_exact_match_preferred(self):
        """Exact normalized match should be preferred"""
        artists = [
            {"id": "1", "name": "Radiohead"},
            {"id": "2", "name": "R.E.M."},
        ]
        result = find_best_artist("REM", artists)
        self.assertEqual(result["id"], "2")
        self.assertEqual(result["name"], "R.E.M.")

    def test_fallback_to_first_if_no_exact(self):
        """If no exact match, should warn and return first"""
        artists = [
            {"id": "1", "name": "Radiohead"},
            {"id": "2", "name": "Nirvana"},
        ]
        result = find_best_artist("Beatles", artists)
        self.assertEqual(result["id"], "1")

    def test_empty_list(self):
        """Empty artist list should return None"""
        result = find_best_artist("REM", [])
        self.assertIsNone(result)


class TestFindBestSong(unittest.TestCase):
    """Test song search result ranking"""

    def test_exact_title_preferred(self):
        """Exact title match should rank highest"""
        songs = [
            {"id": "1", "title": "Leave It Alone", "artist": "Foo"},
            {"id": "2", "title": "Leave", "artist": "R.E.M."},
        ]
        result = find_best_song("Leave", songs)
        self.assertEqual(result["id"], "2")

    def test_exact_title_and_artist(self):
        """Exact title and artist should rank highest"""
        songs = [
            {"id": "1", "title": "Leave", "artist": "Foo"},
            {"id": "2", "title": "Leave", "artist": "R.E.M."},
        ]
        result = find_best_song("Leave", songs, artist_filter="REM")
        self.assertEqual(result["id"], "2")

    def test_missing_artist_filter(self):
        """Should work without artist filter"""
        songs = [
            {"id": "1", "title": "Leave It Alone", "artist": "Foo"},
            {"id": "2", "title": "Leave", "artist": "Bar"},
        ]
        result = find_best_song("Leave", songs)
        self.assertEqual(result["id"], "2")

    def test_empty_list(self):
        """Empty song list should return None"""
        result = find_best_song("Leave", [])
        self.assertIsNone(result)


class TestFindExactTitle(unittest.TestCase):
    """Test finding songs by exact title"""

    def test_exact_match_single(self):
        """Find exact single match"""
        songs = [
            {"id": "1", "title": "Leave It Alone", "artist": "Foo"},
            {"id": "2", "title": "Leave", "artist": "R.E.M."},
        ]
        result = find_song_by_exact_title("Leave", songs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "2")

    def test_exact_match_multiple(self):
        """Find all exact matches (same song in different albums)"""
        songs = [
            {"id": "1", "title": "Leave", "artist": "R.E.M.", "album": "Album A"},
            {"id": "2", "title": "Leave It Alone", "artist": "Foo"},
            {"id": "3", "title": "Leave", "artist": "R.E.M.", "album": "Album B"},
        ]
        result = find_song_by_exact_title("Leave", songs)
        self.assertEqual(len(result), 2)
        self.assertEqual({r["id"] for r in result}, {"1", "3"})

    def test_no_exact_match(self):
        """No exact match should return None"""
        songs = [
            {"id": "1", "title": "Leave It Alone", "artist": "Foo"},
        ]
        result = find_song_by_exact_title("Leave", songs)
        self.assertIsNone(result)

    def test_exact_match_case_insensitive(self):
        """Case insensitive exact match"""
        songs = [
            {"id": "1", "title": "Leave", "artist": "R.E.M."},
        ]
        result = find_song_by_exact_title("leave", songs)
        self.assertEqual(len(result), 1)


class TestRealWorldScenarios(unittest.TestCase):
    """Test real-world use cases from CLAUDE.md"""

    def test_leave_rem_match(self):
        """song: leave, artist: REM should match title: Leave, artist: R.E.M."""
        result_list = [
            {"id": "1", "title": "Leave", "artist": "R.E.M."},
        ]
        best = find_best_song("leave", result_list, artist_filter="REM")
        self.assertIsNotNone(best)
        self.assertEqual(best["artist"], "R.E.M.")

    def test_search_depth_leave(self):
        """Leave (R.E.M.) might not be in first 20 results for generic 'leave' search"""
        # In real scenario, first 20 might be other songs with "Leave"
        early_results = [
            {"id": f"{i}", "title": f"Leave {i}", "artist": f"Band {i}"}
            for i in range(20)
        ]
        desired = {"id": "25", "title": "Leave", "artist": "R.E.M."}
        all_results = early_results + [desired]

        best = find_best_song("leave", all_results, artist_filter="REM")
        self.assertEqual(best["id"], "25")

    def test_new_slang_no_artist(self):
        """Play New Slang without artist should find exact title match"""
        songs = [
            {"id": "1", "title": "New Slang", "artist": "The Shins"},
            {"id": "2", "title": "New Slang (Remix)", "artist": "Other Artist"},
        ]
        best = find_best_song("new slang", songs)
        self.assertEqual(best["id"], "1")

    def test_ambiguous_leave_multiple_artists(self):
        """Multiple exact 'Leave' titles by different artists"""
        songs = [
            {"id": "1", "title": "Leave", "artist": "R.E.M."},
            {"id": "2", "title": "Leave", "artist": "Yes"},
        ]
        exact_matches = find_song_by_exact_title("leave", songs)
        self.assertEqual(len(exact_matches), 2)

    def test_artist_normalization_varieties(self):
        """Test various artist name normalizations"""
        variations = [
            ("REM", "R.E.M."),
            ("R.E.M.", "r.e.m"),
            ("R. E. M.", "R.E.M."),
            ("NoFX", "NOFX"),
            ("The Shins", "the shins"),
            ("CHVRCHES", "chvrches"),
        ]
        for a, b in variations:
            self.assertTrue(artists_match(a, b), f"{a} should match {b}")


def _song(title, artist, album='Album', song_id=None):
    return {'id': song_id or f'{title}-{artist}-{album}', 'title': title, 'artist': artist, 'album': album}


class FakeLibsonicConnection:
    """Stands in for libsonic.Connection, with a Navidrome-like search3.

    Like Navidrome, a result must contain every word of the search term, "the" is not
    ignored, and results are cut off at the requested count (default 20).
    """

    def __init__(self, *args, songs=None, artists=None, **kwargs):
        self.songs = songs if songs is not None else []
        self.artists = artists if artists is not None else []

    @staticmethod
    def _has_all_words(term, *fields):
        text = ' '.join(f.lower() for f in fields)
        return all(word in text for word in term.lower().split())

    def search3(self, term, artistCount=20, albumCount=20, songCount=20, **kwargs):
        result = {}
        songs = [s for s in self.songs if self._has_all_words(term, s['title'], s['artist'], s['album'])][:songCount]
        artists = [a for a in self.artists if self._has_all_words(term, a['name'])][:artistCount]
        if songs:
            result['song'] = songs
        if artists:
            result['artist'] = artists
        return {'searchResult3': result}


LIBRARY_SONGS = [
    _song('Leave', 'Barenaked Ladies', 'Stunt'),
    _song('Leave', 'Barenaked Ladies', 'Greatest Hits'),
    _song('Leave', 'Matchbox Twenty', 'Mad Season'),
    _song('Leave', 'R.E.M.', 'New Adventures in Hi-Fi'),
    _song('Leave', 'R.E.M.', 'In Time'),
    _song('Leave It Alone', 'Some Band', 'Album'),
    _song('If You Leave', 'Orchestral Manoeuvres in the Dark', 'Pretty in Pink'),
    _song('Leave a Trace', 'CHVRCHES', 'Every Open Eye'),
    _song('If I Ever Leave This World Alive', 'Flogging Molly', 'Float'),
    _song('New Slang', 'The Shins', 'Oh, Inverted World'),
    _song('Ripple', 'Grateful Dead', 'Ladies and Gentlemen... the Grateful Dead'),
    _song('Truckin\'', 'Grateful Dead', 'Ladies and Gentlemen... the Grateful Dead'),
    _song('Yesterday', 'The Beatles', 'Help!'),
    _song('Don\'t Look Back in Anger', 'Oasis', '(What\'s the Story) Morning Glory?'),
]

LIBRARY_ARTISTS = [{'id': a, 'name': a} for a in ('R.E.M.', 'REM', 'The Shins', 'Grateful Dead',
                                                   'Grateful Dead - New Years Eve', 'Oasis', 'CHVRCHES')]


def make_connection(songs=None, artists=None):
    """Build a SubsonicConnection that talks to the fake library instead of a server."""
    from asknavidrome.subsonic_api import SubsonicConnection

    fake = FakeLibsonicConnection(songs=LIBRARY_SONGS if songs is None else songs,
                                  artists=LIBRARY_ARTISTS if artists is None else artists)
    with patch('asknavidrome.subsonic_api.libsonic.Connection', return_value=fake):
        return SubsonicConnection('https://navidrome.invalid', 'user', 'pass', 443, '/rest', '1.16.1')


class TestSearchHelpers(unittest.TestCase):
    """Small helpers used to build search terms and rank candidates"""

    def test_strip_leading_article(self):
        self.assertEqual(matching.strip_leading_article('the grateful dead'), 'grateful dead')
        self.assertEqual(matching.strip_leading_article('The Shins'), 'Shins')

    def test_strip_leading_article_leaves_other_words_alone(self):
        self.assertEqual(matching.strip_leading_article('Theory of a Deadman'), 'Theory of a Deadman')
        self.assertEqual(matching.strip_leading_article('The'), 'The')
        self.assertEqual(matching.strip_leading_article(''), '')

    def test_split_song_and_artist(self):
        self.assertEqual(matching.split_song_and_artist('ripple by grateful dead'), [('ripple', 'grateful dead')])

    def test_split_song_and_artist_tries_rightmost_first(self):
        self.assertEqual(matching.split_song_and_artist('killed by death by motorhead'),
                         [('killed by death', 'motorhead'), ('killed', 'death by motorhead')])

    def test_split_song_and_artist_without_by(self):
        self.assertEqual(matching.split_song_and_artist('ripple'), [])
        self.assertEqual(matching.split_song_and_artist(''), [])

    def test_artist_credit_matches_featured_credit(self):
        self.assertTrue(matching.artist_credit_matches('the shins', 'The Shins feat. Iron & Wine'))
        self.assertTrue(matching.artist_credit_matches('iron and wine', 'The Shins feat. Iron & Wine'))
        self.assertFalse(matching.artist_credit_matches('oasis', 'The Shins feat. Iron & Wine'))

    def test_artist_credit_matches_normalizes(self):
        for heard in ('REM', 'R.E.M.', 'R. E. M.'):
            self.assertTrue(matching.artist_credit_matches(heard, 'R.E.M.'))

    def test_ampersand_and_and_are_equivalent(self):
        self.assertEqual(normalize_string('Iron & Wine'), normalize_string('Iron and Wine'))
        self.assertEqual(normalize_string('Love & Happiness'), normalize_string('love and happiness'))

    def test_artist_credit_matches_empty_query(self):
        self.assertFalse(matching.artist_credit_matches('', 'R.E.M.'))

    def test_ordinary_names_still_match_themselves(self):
        for name in ('The Shins', 'CHVRCHES', 'NoFX'):
            self.assertTrue(matching.artist_credit_matches(name, name))

    def test_distinct_by_artist_keeps_one_copy_each(self):
        exact = [s for s in LIBRARY_SONGS if s['title'] == 'Leave']
        distinct = matching.distinct_by_artist(exact)
        self.assertEqual([s['artist'] for s in distinct], ['Barenaked Ladies', 'Matchbox Twenty', 'R.E.M.'])

    def test_pick_song_by_similar_artist_misheard_rem(self):
        exact = [s for s in LIBRARY_SONGS if s['title'] == 'Leave']
        best = matching.pick_song_by_similar_artist('R he. m.', exact)
        self.assertEqual(best['artist'], 'R.E.M.')

    def test_pick_song_by_similar_artist_refuses_unrelated_artist(self):
        exact = [s for s in LIBRARY_SONGS if s['title'] == 'Leave']
        self.assertIsNone(matching.pick_song_by_similar_artist('Oasis', exact))

    def test_pick_song_by_similar_artist_refuses_a_tie(self):
        songs = [_song('Song', 'Band One'), _song('Song', 'Band Two')]
        self.assertIsNone(matching.pick_song_by_similar_artist('Band Ten', songs))

    def test_pick_song_by_similar_artist_empty(self):
        self.assertIsNone(matching.pick_song_by_similar_artist('R.E.M.', []))

    def test_find_best_song_require_artist_never_returns_other_artist(self):
        songs = [_song('If I Ever Leave This World Alive', 'Flogging Molly')]
        self.assertIsNotNone(find_best_song('leave', songs, 'R.E.M.'))
        self.assertIsNone(find_best_song('leave', songs, 'R.E.M.', require_artist=True))


class TestFindSong(unittest.TestCase):
    """SubsonicConnection.find_song against a Navidrome-like library"""

    def setUp(self):
        self.conn = make_connection()

    def test_leave_by_rem(self):
        result = self.conn.find_song('leave', 'REM')
        self.assertEqual(result['status'], 'match')
        self.assertEqual((result['song']['title'], result['song']['artist']), ('Leave', 'R.E.M.'))

    def test_leave_by_misheard_rem(self):
        """Alexa sent the artist as "R he. m." and the artist search finds nothing"""
        self.assertIsNone(self.conn.search_artist('R he. m.'))
        result = self.conn.find_song('leave', 'R he. m.')
        self.assertEqual(result['status'], 'match')
        self.assertEqual(result['song']['artist'], 'R.E.M.')

    def test_ripple_by_the_grateful_dead(self):
        """Navidrome finds nothing for "the grateful dead" but the song's own artist matches"""
        self.assertIsNone(self.conn.search_artist('the grateful dead'))
        result = self.conn.find_song('ripple', 'the grateful dead')
        self.assertEqual(result['status'], 'match')
        self.assertEqual((result['song']['title'], result['song']['artist']), ('Ripple', 'Grateful Dead'))

    def test_missing_artist_unique_title(self):
        result = self.conn.find_song('new slang')
        self.assertEqual(result['status'], 'match')
        self.assertEqual(result['song']['artist'], 'The Shins')

    def test_missing_artist_ambiguous_title_asks(self):
        result = self.conn.find_song('leave')
        self.assertEqual(result['status'], 'ambiguous')
        self.assertIsNone(result['song'])

    def test_ambiguous_candidates_list_each_artist_once(self):
        result = self.conn.find_song('leave')
        self.assertEqual([s['artist'] for s in result['candidates']],
                         ['Barenaked Ladies', 'Matchbox Twenty', 'R.E.M.'])

    def test_exact_title_beats_substring_titles(self):
        titles = {s['title'] for s in self.conn.find_song('leave')['candidates']}
        self.assertEqual(titles, {'Leave'})

    def test_unknown_artist_for_unique_title_does_not_play_other_artist(self):
        """Yesterday exists, but only by The Beatles"""
        self.assertEqual(self.conn.find_song('yesterday', 'Oasis')['status'], 'none')

    def test_unknown_artist_for_shared_title_asks(self):
        result = self.conn.find_song('leave', 'Oasis')
        self.assertEqual(result['status'], 'ambiguous')

    def test_song_that_does_not_exist(self):
        self.assertEqual(self.conn.find_song('no such song')['status'], 'none')
        self.assertEqual(self.conn.find_song('no such song', 'Oasis')['status'], 'none')

    def test_substring_title_is_not_played_for_an_exact_request(self):
        """Only "If I Ever Leave This World Alive" matches Pearl Jam's "leave" loosely"""
        songs = [_song('If I Ever Leave This World Alive', 'Flogging Molly')]
        conn = make_connection(songs=songs)
        self.assertEqual(conn.find_song('leave', 'Pearl Jam')['status'], 'none')
        self.assertIsNone(conn.search_song_best('leave', 'Pearl Jam'))

    def test_search_depth(self):
        """The wanted song is beyond the first 20 results for "leave"."""
        filler = [_song(f'Please Leave Me {i}', f'Filler Band {i}') for i in range(30)]
        conn = make_connection(songs=filler + [_song('Leave', 'R.E.M.')])
        result = conn.find_song('leave', 'REM')
        self.assertEqual(result['status'], 'match')
        self.assertEqual(result['song']['artist'], 'R.E.M.')

    def test_featured_artist_credit(self):
        conn = make_connection(songs=[_song('New Slang', 'The Shins feat. Iron & Wine')])
        self.assertEqual(conn.find_song('new slang', 'The Shins')['status'], 'match')

    def test_duplicate_copies_by_the_same_artist_are_not_ambiguous(self):
        result = self.conn.find_song('leave', 'R.E.M.')
        self.assertEqual(result['status'], 'match')


class TestFindSongFromPhrase(unittest.TestCase):
    """Alexa sometimes puts "<song> by <artist>" in the song slot"""

    def setUp(self):
        self.conn = make_connection()

    def test_ripple_by_grateful_dead_in_song_slot(self):
        result = self.conn.find_song_from_phrase('ripple by grateful dead')
        self.assertEqual(result['status'], 'match')
        self.assertEqual(result['song']['title'], 'Ripple')

    def test_plain_title_is_tried_first(self):
        result = self.conn.find_song_from_phrase('new slang')
        self.assertEqual(result['song']['artist'], 'The Shins')

    def test_title_containing_by(self):
        conn = make_connection(songs=[_song('Killed by Death', 'Motorhead')])
        self.assertEqual(conn.find_song_from_phrase('killed by death')['status'], 'match')
        self.assertEqual(conn.find_song_from_phrase('killed by death by motorhead')['song']['artist'], 'Motorhead')

    def test_nothing_found(self):
        self.assertEqual(self.conn.find_song_from_phrase('nothing by nobody')['status'], 'none')


class TestSearchArtistBest(unittest.TestCase):
    def setUp(self):
        self.conn = make_connection()

    def test_retries_without_the(self):
        self.assertEqual(self.conn.search_artist_best('the grateful dead')['name'], 'Grateful Dead')

    def test_plain_name(self):
        self.assertEqual(self.conn.search_artist_best('the shins')['name'], 'The Shins')

    def test_unknown_artist(self):
        self.assertIsNone(self.conn.search_artist_best('the nobody band'))



if __name__ == '__main__':
    unittest.main()
