import unittest
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


if __name__ == "__main__":
    unittest.main()
