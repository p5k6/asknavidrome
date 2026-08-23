
# AskNavidrome / Music Box Development Instructions

## Project goal

This is a personal fork of AskNavidrome v0.10 used to provide a private Alexa skill called **Music Box** for a household Navidrome music library.

The primary goal is not merely to preserve the upstream implementation. The goal is to make voice playback **reliable, forgiving, and simple enough for young children to use**.

Typical desired interaction:

* "Alexa, open Music Box"
* "Play New Slang"
* "Play Leave by R.E.M."
* "Play music by The Shins"
* "Play Automatic for the People by R.E.M."

Users should not need unnatural phrases such as "play the song X by the band Y" merely to work around Alexa parsing behavior.

## Starting point

This fork started from upstream AskNavidrome v0.10.

Before editing, inspect the repository and understand:

* `skill/app.py`
* `skill/asknavidrome/subsonic_api.py`
* `skill/asknavidrome/controller.py`
* `skill/asknavidrome/media_queue.py`
* `alexa.json`
* `Dockerfile`
* `docker-compose.yml`
* dependency files
* any existing tests or CI configuration

Do not assume the current implementation is correct merely because it is upstream behavior.

## Known real-world failures

### 1. Song search result truncation

A real request for:

* song: `leave`
* artist: `REM`

was correctly sent by Alexa as `NaviSonicPlaySongByArtist`.

Navidrome contains the song:

* title: `Leave`
* artist: `R.E.M.`

However, `search3("leave")` returned only 20 song results and the R.E.M. song was not among those first results.

The existing implementation then failed with:

`I couldn't find a song called leave by REM in the collection.`

Investigate the libsonic/Subsonic `search3` parameters and implement search behavior that does not incorrectly fail simply because the desired track is outside the default result window.

Do not solve this merely by choosing an arbitrarily enormous result count if pagination, targeted searching, or another efficient mechanism would be more robust.

### 2. Artist normalization

Alexa may provide:

`REM`

while Navidrome stores:

`R.E.M.`

These should match.

Matching should be reasonably tolerant of:

* case
* periods
* spaces
* punctuation
* apostrophes
* common Unicode punctuation variations

For example, these should be treated as equivalent for matching purposes:

* `REM`
* `R.E.M.`
* `R. E. M.`

Do not mutate the actual metadata used for display or playback. Normalize only for comparison/ranking.

### 3. Missing artist slot

A real request for:

`Play New Slang by The Shins`

was interpreted by Alexa approximately as:

* intent: `NaviSonicPlaySongByArtist`
* song: `new slang`
* artist: missing

Alexa's own entity resolution knew that "New Slang" was associated with The Shins, but it did not populate the separate artist slot.

The backend should degrade gracefully.

If an artist is absent but an exact normalized song-title search produces exactly one sensible local-library match, play that song.

Example:

`Play New Slang`

should play `New Slang` by The Shins when that is the only exact-title match in Navidrome.

If several exact-title matches exist, do not silently choose an obviously arbitrary song. Prefer a short useful response asking for clarification, such as which artist the user means.

### 4. Current song-by-artist matching is brittle

The existing implementation effectively:

1. searches for an artist,
2. selects the first artist search result,
3. searches for the song,
4. keeps songs whose `artistId` equals that first artist ID.

Do not assume the first fuzzy search result is the requested artist.

A better implementation should rank actual metadata matches and favor exact normalized matches.

For a song+artist request, prefer matching using the song result's own metadata where practical:

* exact normalized song title
* exact normalized artist name

A song named `Leave It Alone` should not satisfy a request for `Leave`.

### 5. Search helpers have similar assumptions

Review artist, album, playlist, genre, favorites, and other user-facing lookup paths for the same classes of problems:

* silently taking the first fuzzy result
* default API result limits
* case-only comparisons
* punctuation-sensitive comparisons
* missing or empty slots
* empty result lists
* direct `[0]` or `[1]` indexing without verifying list length
* ambiguous matches
* assumptions that Alexa always supplies every expected slot

Fix closely related problems when doing so clearly improves reliability.

This is explicitly allowed. Do not limit the work to the two examples above if inspection reveals the same bug pattern elsewhere.

## Alexa interaction model

The household-facing invocation name is:

`music box`

Keep `alexa.json` consistent with that name.

Preserve existing intent names unless changing them provides a clear benefit and the corresponding Python handlers and model are updated together.

Do not immediately replace the existing Alexa model with a completely different architecture. First make the backend tolerant of the imperfect slot values Alexa actually sends.

However, you may improve `alexa.json` if inspection or testing indicates that additional natural sample utterances materially improve usability.

Optimize for phrases humans, especially children, naturally say.

Avoid requiring users to say phrases like:

* "by the band"
* "by the artist"

when ordinary phrases such as:

* "play New Slang"
* "play Leave by R.E.M."
* "play The Shins"
* "play music by The Shins"

can reasonably be supported.

Alexa entity-resolution metadata may be inspected and used as a hint where useful, but it should not override the contents of the user's local Navidrome library or become a hard dependency on Amazon's catalog.

## Matching behavior

Prefer a reusable matching/ranking implementation rather than duplicating slightly different normalization logic in multiple Alexa handlers.

Suggested priority for song matching:

1. Exact normalized title + exact normalized artist, when artist is supplied.
2. Exact normalized title when no artist is supplied and there is a single unambiguous match.
3. Reasonable fallback matching only when confidence is high.
4. Ask for clarification or report no match rather than playing an unrelated track.

Do not make fuzzy matching so permissive that a request for one song routinely plays another.

For duplicate copies of the same recording in multiple albums/releases, it is acceptable to choose one sensible copy rather than forcing unnecessary clarification if title and artist both match.

## User experience

Alexa responses should be short and natural.

Good:

* `Playing Leave by R.E.M.`
* `I found more than one song called Leave. Which artist?`
* `I couldn't find New Slang.`

Avoid developer-oriented or verbose responses.

The household use case values reliability and ease of use over exposing internal detail.

## Testing

Add automated tests if the project does not already adequately cover this logic.

Search/matching logic should be testable without:

* a real Alexa device
* the real household Navidrome server
* real credentials
* internet access

Use fixtures/mocks representing actual Subsonic results.

At minimum, cover:

### Song + artist normalization

Input:

* song: `leave`
* artist: `REM`

Available result:

* title: `Leave`
* artist: `R.E.M.`

Expected: match.

### Search result depth

The desired exact song may occur after the first 20 generic search results.

Expected: it can still be found.

### Missing artist

Input:

* song: `new slang`
* artist: absent

Available exact-title results:

* `New Slang` by `The Shins`

Expected: match and play.

### Ambiguous title

Input:

* song: `leave`
* artist: absent

Available exact-title results from several artists.

Expected: do not arbitrarily choose one.

### Exact title preference

Input:

* song: `leave`

Results include:

* `Leave`
* `Leave It Alone`
* `If You Leave`
* `Leave a Trace`

Expected: exact `Leave` matches rank above substring matches.

### Artist normalization

Inputs such as:

* `REM`
* `R.E.M.`
* `R. E. M.`

should match the same artist.

Also test ordinary names such as:

* `The Shins`
* `CHVRCHES`
* `NoFX`

to ensure normalization does not damage normal matching.

## Docker development workflow

The upstream Dockerfile currently performs a fresh:

`git clone https://github.com/rosskouk/asknavidrome.git`

during image creation.

That means a normal Docker build can accidentally package upstream source rather than changes in this local fork.

Fix the Dockerfile so that development/production images are built from the **checked-out local source tree**, normally using `COPY` from the Docker build context.

A local command such as:

`docker build .`

or:

`docker compose build`

must actually contain the code from the current checkout.

Keep the resulting image straightforward and reasonably small.

## Security

Never commit:

* Navidrome usernames/passwords
* Alexa API access tokens
* cookies
* private keys
* `.env` files containing credentials
* household URLs if they have been intentionally kept private

Use environment variables and an `.env.example` containing placeholders where appropriate.

The Alexa Skill ID is an identifier rather than a password, but there is still no need to hardcode a household-specific value into generic source code.

Do not weaken existing Alexa request verification or Skill ID validation.

Do not add external cloud services, analytics, telemetry, databases, LLM APIs, or other dependencies unless they are genuinely necessary. This service should remain inexpensive and self-hosted.

## Scope and engineering judgment

You have latitude to refactor code when doing so improves correctness, readability, testability, or consistency.

You may fix adjacent bugs discovered while tracing these workflows.

Prefer coherent improvements over narrowly patching individual examples.

However:

* do not rewrite the entire application without a compelling reason
* preserve existing working playback/queue behavior
* preserve AudioPlayer support
* preserve existing next/previous/pause/resume behavior
* preserve playlist, favorites, genre, album, artist, star/unstar, and song-detail functionality unless intentionally improving it
* preserve the existing asynchronous/background strategy where necessary to stay within Alexa response-time limits
* do not introduce heavyweight infrastructure

## Workflow

Before making substantial edits:

1. Inspect the repository.
2. Trace the Alexa intent handlers through the Subsonic API wrapper and playback queue.
3. Identify the root causes of the known failures.
4. Look for the same bug patterns in related handlers.
5. Briefly state the implementation plan.
6. Implement the changes.
7. Add or update tests.
8. Run all available tests/linting.
9. Build the Docker image from the local checkout.
10. Report:

* files changed
* behavior changed
* tests run
* remaining limitations
* any Alexa interaction-model changes that must be copied/rebuilt in the Developer Console

Do not commit, push, open pull requests, change remote infrastructure, or use real credentials unless explicitly asked.
