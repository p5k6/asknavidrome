"""Tests for the Alexa intent handlers in app.py.

app.py is imported with a fake Navidrome behind it, so these run without a server,
credentials, a network connection or an Alexa device. Each test replays a request
that Alexa really sent.
"""
import os
import re
import unittest
from unittest.mock import MagicMock, patch

from ask_sdk_core.response_helper import ResponseFactory
from ask_sdk_model import Intent, IntentRequest, RequestEnvelope, Slot
from ask_sdk_model.simple_slot_value import SimpleSlotValue

from tests import make_connection

FAKE_ENV = {
    'NAVI_SKILL_ID': 'amzn1.ask.skill.00000000-0000-0000-0000-000000000000',
    'NAVI_URL': 'https://navidrome.invalid',
    'NAVI_USER': 'user',
    'NAVI_PASS': 'pass',
    'NAVI_PORT': '443',
    'NAVI_API_PATH': '/rest',
    'NAVI_API_VER': '1.16.1',
    'NAVI_SONG_COUNT': '50',
    'NAVI_DEBUG': '0',
}

app = None


def setUpModule():
    global app
    with patch.dict(os.environ, FAKE_ENV), \
            patch('asknavidrome.subsonic_api.SubsonicConnection', return_value=MagicMock()):
        import app as app_module
        app = app_module


def request_for(intent_name, **slots):
    """Build the handler input Alexa would send for an intent with the given slot values."""
    slot_objects = {name: Slot(name=name, value=value, slot_value=SimpleSlotValue(value=value))
                    for name, value in slots.items()}
    envelope = RequestEnvelope(request=IntentRequest(intent=Intent(name=intent_name, slots=slot_objects)))

    handler_input = MagicMock()
    handler_input.request_envelope = envelope
    handler_input.attributes_manager.session_attributes = {}
    handler_input.response_builder = ResponseFactory()
    return handler_input


def spoken(response):
    """The plain text of what Alexa would say."""
    ssml = response.output_speech.ssml if response and response.output_speech else ''
    return re.sub(r'</?speak>', '', ssml)


class HandlerTestCase(unittest.TestCase):
    def setUp(self):
        patches = [
            patch.object(app, 'connection', make_connection()),
            patch.object(app, 'play_queue', MagicMock()),
            patch.object(app.controller, 'enqueue_songs'),
            patch.object(app.controller, 'start_playback', side_effect=lambda mode, speech, *a, **k: speech),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.enqueue = app.controller.enqueue_songs

    def played_song_id(self):
        """The ID of the song that was queued, or None if nothing was."""
        if not self.enqueue.called:
            return None
        return self.enqueue.call_args[0][2][0]


class TestPlaySongByArtistHandler(HandlerTestCase):
    def handle(self, **slots):
        handler_input = request_for('NaviSonicPlaySongByArtist', **slots)
        return handler_input, app.NaviSonicPlaySongByArtist().handle(handler_input)

    def test_leave_by_rem(self):
        _, result = self.handle(song='leave', artist='REM')
        self.assertEqual(result, 'Playing Leave by R.E.M.')

    def test_leave_by_misheard_rem(self):
        """Seen in the logs: the artist arrived as "R he. m." """
        _, result = self.handle(song='leave', artist='R he. m.')
        self.assertEqual(result, 'Playing Leave by R.E.M.')

    def test_ripple_by_the_grateful_dead(self):
        """Seen in the logs: the artist arrived as "the grateful dead" """
        _, result = self.handle(song='ripple', artist='the grateful dead')
        self.assertEqual(result, 'Playing Ripple by Grateful Dead')

    def test_new_slang_without_artist(self):
        _, result = self.handle(song='new slang')
        self.assertEqual(result, 'Playing New Slang by The Shins')

    def test_ambiguous_song_asks_and_remembers_the_options(self):
        handler_input, result = self.handle(song='leave')
        self.assertIsNone(self.played_song_id())
        self.assertIn('more than one song called leave', spoken(result))
        attrs = handler_input.attributes_manager.session_attributes
        self.assertEqual({s['artist'] for s in attrs['ambiguous_songs']},
                         {'Barenaked Ladies', 'Matchbox Twenty', 'R.E.M.'})

    def test_unknown_song_says_so_briefly(self):
        _, result = self.handle(song='no such song', artist='Oasis')
        self.assertIsNone(self.played_song_id())
        self.assertEqual(spoken(result), 'I couldnt find no such song by Oasis.')

    def test_does_not_play_a_different_artists_song(self):
        _, result = self.handle(song='yesterday', artist='Oasis')
        self.assertIsNone(self.played_song_id())
        self.assertIn('couldnt find yesterday by Oasis', spoken(result))

    def test_missing_song_slot_asks_instead_of_crashing(self):
        _, result = self.handle(artist='Oasis')
        self.assertIsNone(self.played_song_id())
        self.assertIn('What song', spoken(result))


class TestPlaySongHandler(HandlerTestCase):
    def handle(self, song):
        handler_input = request_for('NaviSonicPlaySong', song=song)
        return handler_input, app.NaviSonicPlaySong().handle(handler_input)

    def test_ripple_by_grateful_dead_in_the_song_slot(self):
        """Seen in the logs: the whole phrase arrived in the song slot"""
        _, result = self.handle('ripple by grateful dead')
        self.assertEqual(result, 'Playing Ripple by Grateful Dead')

    def test_ripple(self):
        _, result = self.handle('ripple')
        self.assertEqual(result, 'Playing Ripple by Grateful Dead')

    def test_ambiguous_title_lists_each_artist_once_and_remembers_options(self):
        handler_input, result = self.handle('leave')
        self.assertEqual(spoken(result),
                         'I found more than one song called leave, by Barenaked Ladies, Matchbox Twenty, R.E.M.. Which artist?')
        self.assertEqual(len(handler_input.attributes_manager.session_attributes['ambiguous_songs']), 3)

    def test_not_found(self):
        _, result = self.handle('no such song')
        self.assertEqual(spoken(result), 'I couldnt find no such song.')

    def test_missing_song_slot(self):
        handler_input = request_for('NaviSonicPlaySong')
        result = app.NaviSonicPlaySong().handle(handler_input)
        self.assertIn('What song', spoken(result))


class TestClarifyArtistHandler(HandlerTestCase):
    def handle(self, artist, session=None):
        handler_input = request_for('NaviSonicClarifyArtist', artist=artist)
        if session:
            handler_input.attributes_manager.session_attributes.update(session)
        return handler_input, app.NaviSonicClarifyArtist().handle(handler_input)

    def test_play_ripple_without_a_pending_question(self):
        """Seen in the logs: "play Ripple" arrived here and got "I didn't catch that" """
        _, result = self.handle('ripple')
        self.assertEqual(result, 'Playing Ripple by Grateful Dead')

    def test_unprompted_artist_name_plays_that_artist(self):
        with patch.object(app.NaviSonicPlayMusicByArtist, 'handle', return_value='ARTIST') as artist_handler:
            _, result = self.handle('the shins')
        self.assertEqual(result, 'ARTIST')
        artist_handler.assert_called_once()

    def test_unprompted_unknown_name(self):
        _, result = self.handle('zzz nothing')
        self.assertEqual(spoken(result), 'I couldnt find zzz nothing.')

    def test_answering_which_artist(self):
        handler_input = request_for('NaviSonicPlaySong', song='leave')
        app.NaviSonicPlaySong().handle(handler_input)
        session = dict(handler_input.attributes_manager.session_attributes)

        _, result = self.handle('R.E.M.', session)

        self.assertEqual(result, 'Playing Leave by R.E.M.')

    def test_answering_with_a_misheard_artist(self):
        handler_input = request_for('NaviSonicPlaySong', song='leave')
        app.NaviSonicPlaySong().handle(handler_input)
        session = dict(handler_input.attributes_manager.session_attributes)

        _, result = self.handle('R he. m.', session)

        self.assertEqual(result, 'Playing Leave by R.E.M.')

    def test_answering_with_an_artist_that_is_not_an_option(self):
        handler_input = request_for('NaviSonicPlaySong', song='leave')
        app.NaviSonicPlaySong().handle(handler_input)
        session = dict(handler_input.attributes_manager.session_attributes)

        _, result = self.handle('Oasis', session)

        self.assertIsNone(self.played_song_id())
        self.assertIn('Which artist did you mean', spoken(result))

    def test_missing_artist_slot(self):
        handler_input = request_for('NaviSonicClarifyArtist')
        result = app.NaviSonicClarifyArtist().handle(handler_input)
        self.assertIn("didnt catch that", spoken(result))


if __name__ == '__main__':
    unittest.main()
