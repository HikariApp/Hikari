# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Version entries are grouped by their release tag date. Undated work that
predates the first tag is collected under the initial `v1.0.0` release.

---

## [v3.5.1] - 2026-09-01
### Fixed
- `discord.opus.OpusNotLoaded` crash on every incoming voice packet when
  recording: the slim Docker runtime base shipped without libopus, needed to
  decode Opus to PCM. `libopus0` is now installed in the runtime stage.
- pydub `Couldn't find ffmpeg or avconv` warning and non-functional audio
  mixing: `ffmpeg` is now installed in the runtime stage. Both are native
  system libraries that installing pydub via `uv` did not provide.
- `AttributeError: 'BetterPlayer' object has no attribute 'is_listening'`
  during shutdown while music was playing: `close()` assumed every voice
  client was a recorder client. The listening teardown is now guarded so
  plain music clients disconnect cleanly.
- Recorder guard checked global `bot.voice_clients` state instead of the
  command's own guild, so the bot being connected in any server blocked
  recording in every other server. The guard now uses `guild.voice_client`,
  matching the per-guild logic the music player already used.
### Changed
- `record` no longer requires the invoker to be in a voice channel when the
  bot is already connected; it starts recording in the bot's current channel.
  The guard also refuses cleanly if the bot is connected in a non-recordable
  state rather than failing later.

## [v3.5.0] - 2026-09-01
### Added
- Recorder-aware guards in the music player: `join`/`play` and `ensurePlayable`
  now respond with a clear ephemeral error when the voice client is currently
  occupied by the voice recorder, instead of misbehaving.
- Explicit offline-presence nudge during shutdown to work around an upstream
  discord.py issue where the bot lingers as online after the connection closes.
- `pydub` dependency for recorder audio mixing and silence handling
  (now used by `_recorderSink.py`).
### Changed
- Restructured the voice recorder: retired the standalone `VoiceRecorder` cog
  in favor of `_recorderSink.py`.
- Reworked shutdown signal handling: `SIGTERM` is now routed through
  `default_int_handler` so Docker stops follow the same proven
  `KeyboardInterrupt` path `bot.run()` already handles cleanly, rather than a
  custom loop signal handler that fought `bot.run()`.
- `close()` now tears down voice clients first (while the gateway is still up):
  `stop_listening()` followed by `disconnect(force=True)` under a 0.2s timeout,
  tolerating and logging timeouts/failures so shutdown never hangs.
- Tidied `startup.py` imports (`Intents`/`Status`/`math`/`signal`) and comments.
- Bumped project version to `3.5.0`.
### Fixed
- Health endpoint no longer emits `NaN` for `latency_ms` before the first
  heartbeat; latency is now guarded with `math.isfinite()`.
- `respondEmbed` passes `view or MISSING` to `interaction.response.send_message`,
  so a `None` view no longer breaks the ephemeral response path.
- `on_voice_state_update` no longer raises an unhandled
  `ServerDisconnectedError` when sending the "left the voice channel"
  notification during shutdown or a gateway drop; the send is now guarded
  and the disconnect is logged as a warning.

## [v3.3.0] - 2026-08-31
### Added
- Slim Docker image via multi-stage build on a slim base.
### Changed
- Centralized voice error handling and reworked the `moveAll` signature.
- Replaced dependencies, bumped requirements, and integrated `uv` properly.
- Wording corrections across the voice module.
### Fixed
- Forced self-defined VC and mute functions to take positional arguments, fixing "move all members" failures.
- `TypeError: bad operand type for unary +: 'str'` caused by a stray comma.
- Added exception handlers for `ChannelNotFound` cases in voice.
### Removed
- Unused `VoiceChannelConfig`.

## [v3.2.2] - 2026-08-29
### Changed
- `lockchannel`: concurrent bulk operations and hardened embed delivery.

## [v3.2.1] - 2026-08-28
### Added
- Volume confirmation prompt for high levels in the music player.
### Fixed
- Cog error handling now uses the real `cog_command_error` hook across cogs, with a handled-error guard.
- `musicQueue`: restored missing logging and fixed the logger variable name.
- Numeric arguments now work on prefix-invoked hybrid commands.
- `repeat` command no longer unresponsive when disabled.

## [v3.1.7] - 2026-08-27
### Added
- Core response layer now supports reply and private send with optional `deleteAfter`.
### Changed
- Replaced boolean flags in `respondEmbed` with a `ResponseTarget` enum and added interaction acknowledgement.
- Migrated `ownerOnly`, `MusicPlayer`, and moderation call sites to the unified response-embed API.
- Converted common moderation commands to hybrid commands.

## [v3.1.0] - 2026-08-26
### Added
- Hardened `extensionsHandler` with a customized boolean checker.
### Changed
- Complete overhaul of the application startup and restart logic.
- Refined docstrings across moderation, general extensions, and other modules.
- Added license info, `SPDX-License-Identifier`, and copyright headers for self-authored modules.
### Fixed
- Handle `SIGTERM` for graceful shutdown under Docker.

## [v3.0.0] - 2026-08-25
### Added
- Default metadata handling for `TrackType.APPLE_MUSIC`.
### Changed
- Renamed all helpers and reorganized files.
- Rewrote the plugin control system.
- Separated `BetterPlayer` and `BetterQueue` for cleaner management.
- Renamed `GetDetailIPv4Info` to `IPv4info` everywhere.
### Removed
- Legacy track command.

## [v2.9.7] - 2026-08-22
### Fixed
- Embed no longer renders incorrectly when a track has no artwork attached.

## [v2.9.3] - 2026-08-21
### Added
- Standardized variables inside the music player and added helper utilities.
### Changed
- Optimized the flow when previous/skip actions are executed.
- Updated `README.md` and `LICENSE`.
### Fixed
- Skipping no longer breaks after the latest rewrite.
- Restored missing logic in the `nextTrack` session.
- Tracks no longer remain paused after skip/previous when previously paused.

## [v2.8.5] - 2026-08-20
### Fixed
- Overhauled the "repeat all" logic in the music player.
- Fixed un-awaited Discord responses in the music player.
- Overhauled `isFinalTrack` and skipping logic.
### Changed
- Simplified special-source handling for Plex.

## [v2.7.3] - 2026-04-07
### Fixed
- Music player events could not be listened to after switching from pomice to lava-lyra.
- Corrected the image source URL for Hikari's profile.
### Changed
- Updated the contact email for reporting incidents.

## [v2.7.0] - 2026-03-20
### Changed
- Replaced the music player module from **pomice** with **lava-lyra** to adapt to Discord DAVE changes before 2026-03-31, and refactored the player accordingly.

## [v2.6.6] - 2026-02-07
### Fixed
- Bot no longer goes offline when `player.nextTrack()` dies.
### Changed
- Refactored all history carried over from the old repository, with minor optimization.

## [v2.2.5] - 2025-10-17
### Changed
- Rewrote the entire music player system.

## [v2.2.0] - 2025-04-07
### Added
- Proper error handling when a user tries to start a new conversation in an existing thread (`ChatBot`).
### Changed
- Replaced several outdated emoji icons.

## [v2.1.8] - 2025-04-06
### Changed
- Completely rewrote `ChatGPT.py` around a new thread structure and renamed it to `ChatBot.py`.
- Updated models from GPT-4/GPT-4o to GPT-4o/GPT-4.5.
- `reset` now requires admin permission.
### Fixed
- Heartbeat failures resolved by adopting `AsyncOpenAI`.

## [v2.1.7] - 2025-04-01
### Changed
- Completely rewrote `SendFromInput.py`, renamed it to `SendAsBot.py`, and overhauled its error handling.
- `SendAsBot` now requires admin permission.

## [v2.1.5] - 2025-03-31
> **Important update.**
### Changed
- Rebranded the bot under a new name after the original was deleted, and resumed development.
- Refactored `startup.py` for another server migration and updated all environment variables.
- Transferred application ownership from an individual to a newly created organization.
- Rotated the OpenAI service token.
### Removed
- Large amounts of redundant code and comments.

## [v2.1.4] - 2025-02-09
### Fixed
- OpenAI issues after switching servers.

## [v2.1.0] - 2024-12-25
### Fixed
- Overflow error when a livestream is playing.

## [v2.0.6] - 2024-12-22
### Changed
- Rewrote the message formatter for universal language support.
### Fixed
- Minor issues in `ChatGPT.py`.

## [v2.0.3] - 2024-12-21
### Changed
- Rewrote `startup.py` with a fully asynchronous approach for maximum resource optimization.
- Replaced Microsoft Azure OpenAI with the OpenAI service and refactored its error handling.
- Switched from `openai.chat.completions` to `openai.beta.assistants` for better integration.
### Added
- File-upload support; uploaded files are stored server-side with the file ID persisted in the database.
### Removed
- Multiprocessing.
- Custom prompting (due to predictable edge-case issues).

## [v2.0.1] - 2024-12-15
### Changed
- Rewrote the MongoDB connection and logic using `motor_asyncio`.
- Improved custom-file handling in the music player.
### Removed
- Legacy plugins directory (no longer used).

## [v2.0.0] - 2024-12-06
> **MongoDB database integration.**
### Added
- Custom welcome messages (defaults unchanged).
- Configurable per-server toggle for deleting messages in the system channel.
- Automatic un-mute handling after a mute expires (applied on next startup if offline).
### Changed
- Rewrote `startup.py` for database integration.
- `chat_message` and `chat_history` are now stored entirely in the database.
- Mute data (type, ending time, etc.) is now stored entirely in the database.
- Moved `MessageFiltering.py` from `general` to `moderation`.

## [v1.9.4] - 2024-12-04
### Changed
- Rewrote `move_all()` and `end` in `VoiceChannel.py` for better resource usage.
- Migrated the application to Hetzner Cloud from Microsoft Azure.
### Fixed
- Temporary fix for Lavalink web-playback issues.
### Removed
- `push_to_docker.yml` workflow.

## [v1.9.3] - 2024-12-01
### Changed
- Recreated `requirements.txt`, removing redundant dependencies.
- Refactored `VoiceChannel.py` for embed support.

## [v1.6.8] - 2024-11-29
### Added
- Docker Compose support.
### Changed
- Moved `plugins` to `configs/plugins`.
- Refactored environment variables into a publishable example.
### Fixed
- `startup.py` issues under Docker Compose.

## [v1.5.3] - 2024-11-22
### Added
- Version tagging support.
### Changed
- Moved the Docker image to the GitHub Container Registry (GHCR).

## [v1.5.2] - 2024-11-15
### Changed
- Rewrote and simplified `ChatGPT.py`.
- Rephrased the duration message into a more readable form for all time-based mutes/timeouts.

## [v1.5.1] - 2024-11-11
### Added
- Nightcore filter support in the music player.
### Changed
- Rewrote kick/mute duration parameters as time-string objects.
- Mute duration is now infinite when no duration is passed to `mute()`/`vmute()`.
### Fixed
- Muting now works correctly in voice channels.

## [v1.5.0] - 2024-11-07
### Changed
- Rewrote and refactored most of the moderation section.
- Separated voice kick/mute into `vkick()`, `vmute()`, and `vumute()` in `VoiceChannel.py`.
- Improved error handling throughout.

## [v1.4.6] - 2024-10-28
### Changed
- Improved error handling for unsupported audio files in the music player.

## [v1.4.5] - 2024-10-23
### Added
- `IPv4info.py`.
### Changed
- Rewrote the shutdown/restart logic using multiprocessing.
- Changed the service port from 8080 to 3000.
### Removed
- `restarter.py` (superseded by the rewrite).

## [v1.4.4] - 2024-10-22
### Added
- `VoiceRecorder.py`, re-adding voice-channel recording after the discord.py migration.
- New `custom_recording` directory under `plugins`.

## [v1.4.3] - 2024-10-16
### Changed
- Rewrote the ChatGPT input logic and improved markdown formatting.
- Re-added custom-prompt support.
### Security
- Rotated the application and Azure OpenAI API keys.

## [v1.4.2] - 2024-10-13
### Added
- `CustomEmbed.py`.
### Changed
- Repeat and autoplay are now boolean options.

## [v1.4.1] - 2024-10-01
### Fixed
- Upcoming tracks now display correctly.
### Changed
- Improved the autoplay feature.

## [v1.4.0] - 2024-09-30
> **Wavelink-based music engine.**
### Added
- Wavelink v3.4.1 integration; the player system was rewritten into a dedicated `MusicPlayer.py`.
- `VoiceChannelFallbackConfig.py` for per-guild fallback text-channel configuration.
- `nowplaying()` to view the current track's information.
- Git branch workflow for all branches.
### Changed
- `VoiceChannel.py` now handles only basic voice operations; all music commands moved out.
- Moved `ErrorHandling.py` into `errorhandling/`.
- Bumped the Docker Python image to `3.12.6-bookworm`.
### Fixed
- YouTube videos/streams can now be played.
- Custom track information now displays correctly.

## [v1.3.6] - 2024-09-07
### Changed
- Switched to Azure OpenAI (from OpenAI) for better GPT-4o support; renamed `OPENAI_API_KEY` to `AZUREOPENAI_API_KEY`.
- Rewrote and improved error handling for the Azure OpenAI migration.

## [v1.3.5] - 2024-08-17
### Added
- New poll system (`Poll.py`); the previous system was renamed to `Vote.py`.
### Changed
- Fine-tuned the ChatGPT prompt and updated emoji.
- Optimized the `NotBotOwnerError()` response.
### Other
- Bot verified and transferred to a team.

## [v1.3.4] - 2024-07-30
### Added
- Support for user-installed applications in ChatGPT (file rewritten to accommodate this).

## [v1.3.3] - 2024-07-21
### Fixed
- Adding multiple tracks to the queue.

## [v1.3.2] - 2024-07-20
### Added
- `ErrorHandling.py`; all custom errors were moved here.

## [v1.3.1] - 2024-07-18
### Changed
- Improved ChatGPT prompting.
- `resetgpt()` is now bot-owner only.

## [v1.3.0] - 2024-07-16
### Fixed
- Assorted ChatGPT issues.

## [v1.2.9] - 2024-06-16
### Changed
- Re-separated cogs by category and renamed `cogs` back to `general`.
- Rewrote the extension-loading logic in `startup.py`.

## [v1.2.8] - 2024-06-14
### Changed
- Mostly rewrote the user/guild ban logic.
### Fixed
- Guild ban now functions correctly.
- Added error handling for `vkick()`.

## [v1.2.5] - 2024-06-11
### Added
- Volume control and a `replay()` command.
- Repeat one/all tracks.
- Track paging with a dropdown menu.
### Changed
- Rewrote the entire player and queue logic to support the above.
- Renamed queue variables (`music_queue` → `track_queue`, etc.).
### Fixed
- Skipping to the last track in the queue.
- Queue display with more than 15 tracks, and the last-track display.

## [v1.2.2] - 2024-06-01
### Changed
- `shutdown()` restored to its original functionality and marked as **self-destruct**.
- The bot now returns an error when no users are present in a VC during a move.
### Removed
- `restart()` (compatibility issues).
### Infrastructure
- Rolled back to Microsoft Azure with the same structure as Google Cloud Run.

## [v1.2.1] - 2024-05-13
### Added
- `systeminfo()` command for the bot owner.

## [v1.2.0] - 2024-05-13
### Changed
- The bot now runs as a Quart app inside a Docker container.
- Rewrote `startup.py` with breaking logic changes for the migration.
### Removed
- `is_restarting` variable and the `shutdown()` command (temporarily).
### Infrastructure
- Migrated from Microsoft Azure to the Google Cloud Run API.

## [v1.1.5] - 2024-04-04
### Added
- `restart()` command and `restarter.py` for the bot owner (guarded by `NotBotOwnerError()`).
### Changed
- Replaced `os.system()` with `subprocess`.
- Optimized message handling; non-sticker messages in the system channel are now auto-deleted.

## [v1.1.4] - 2024-03-19
### Added
- Bot-owner shutdown via `<prefix>shutdown` (guarded by `NotBotOwnerError()`).
### Changed
- Optimized error handling in `ChatGPT.py`.

## [v1.1.0] - 2024-03-10
### Fixed
- Crashes when displaying users with default avatars.
### Changed
- Optimized the structure of `ReactingMessages.py`.

## [v1.0.8] - 2024-02-28
### Changed
- Rewrote `startup.py` and updated several return messages in `VoiceChannel.py`.

## [v1.0.7] - 2024-02-26
> **Framework migration: pycord → discord.py.**
### Added
- Custom status support.
### Removed
- `recording_vc()` (privacy concerns).

## [v1.0.6] - 2024-02-24
### Added
- "Send as silent message" option in `SendFromInput.py`.
### Changed
- Grouped major error messages into dedicated classes.

## [v1.0.5] - 2024-02-03
### Added
- Playback of custom audio files (mp3/wav).
### Changed
- Replaced `eyed3` with `tinytag`.
### Fixed
- Custom files not playing in the music player.

## [v1.0.4] - 2024-01-30
### Changed
- Merged the dev build into stable.
- The player now notifies the user when the last track is skipped or the queue is exhausted.
### Fixed
- Player resetting itself when moving between voice channels.
- Crashes when displaying users with default avatars.
- Skip attempts continuing after the final track finished.

## [v1.0.3] - 2024-01-23
### Added
- Lite version of the music player.
- Voice-channel recording.
### Changed
- Rewrote `Poll.py` for multi-server support.

## [v1.0.2] - 2024-01-21
### Added
- Beta music player.
### Changed
- Rewrote `VoiceChannel.py` toward full music-player support.
- Optimized the displayed name in `DisplayUserInfo.py`.

## [v1.0.1] - 2024-01-13
### Added
- `move_bot()` command in `VoiceChannel.py`.
### Infrastructure
- Migrated hosting to Microsoft Azure.

## [v1.0.0] - 2024-01-08
> Initial public release on GitHub. Consolidates all pre-release development
> from 2023-10-03 onward.
### Added
- Initial bot with **MessageFiltering** and **Greetings**.
- Moderation: `ban_guild()` and `LockChannel.py` (with anti-raid activate/deactivate).
- `DisplayUserInfo`, `GetBannedList`, and voice-channel commands.
- OpenAI-powered `ChatGPT.py`, including chat history (up to 15 recent conversations), `reset()`, and tuned defaults.
- `ChangeStatus.py` with full activity-type support.
- `ReactingMessages.py` (add/remove/list/clear reactions).
- `SendFromInput.py` (renamed from `SendMessage.py`) with single-attachment support.
- Login-failure handling in the main entry point.
### Changed
- Migrated the framework from **discord.py** to **pycord**.
- Updated the OpenAI library from 0.27.0 to 1.0.0 and adopted the new response API.
- Reorganized all modules into a `cogs` directory; renamed `MainBOT.py` to `startup.py`.
- Bot logic no longer DMs bot accounts a welcome message.
### Infrastructure
- Migrated the project from Repl.it to GitHub and Dockerized the application.

---

## Pre-versioning History (2023–2024)

> These entries predate the project's adoption of Semantic Versioning (v1.5.3).
> They have been condensed from a much more granular daily log; full line-level
> detail remains in the git history. Grouped by month, most recent first.

### 2024-09 → 2024-11 — Wavelink, refactors, new cogs
- Implemented Wavelink v3.4.1 and split the player into a new `MusicPlayer.py`;
  fixed YouTube video/stream playback. `VoiceChannel.py` now handles only basic
  voice operations.
- Added `VoiceChannelFallbackConfig.py`, `CustomEmbed.py`, `VoiceRecorder.py`,
  `IPv4info.py`, and a `nowplaying()` command; added a nightcore filter.
- Moved custom errors into `errorhandling/ErrorHandling.py`.
- Rewrote shutdown/restart with multiprocessing; removed `restarter.py`; changed
  the port from 8080 to 3000.
- Refactored the moderation section; separated voice kick/mute into `vkick()`,
  `vmute()`, `vumute()`; rewrote time parameters as time-string objects.

### 2024-08 → 2024-09 — Polls, Azure OpenAI, git & Docker
- Introduced a new poll system (`Poll.py`); renamed the old one `Vote.py`. Bot
  verified and transferred to a team.
- ChatGPT: added User-Installed application support; switched to Azure OpenAI for
  GPT-4o support.
- Added git workflow for all branches; bumped the Docker Python image to
  3.12.6-bookworm.

### 2024-06 → 2024-07 — Music player maturity, ban rewrite
- Added volume control, `replay()`, and repeat-one/all; rewrote the queue system
  with dropdown-based track paging.
- Rewrote user/guild ban logic.
- Re-separated cogs by category and renamed `cogs` back to `general`.

### 2024-05 → 2024-06 — Cloud migrations
- Migrated Azure → Google Cloud Run, running as a Quart app in Docker; later
  rolled back to Azure.
- Added the `systeminfo()` command.
- Temporarily removed and later restored `shutdown()`/`restart()` around the
  migrations.

### 2024-02 → 2024-04 — Framework swap, moderation
- Added custom audio (mp3/wav) support; replaced `eyed3` with `tinytag`.
- Migrated Pycord → discord.py; added custom status; removed voice recording for
  privacy.
- Added owner-only `shutdown`/`restart` (raising `NotBotOwnerError` for others);
  replaced `os.system()` with `subprocess`.
- `MessageFiltering` now auto-deletes non-sticker messages in the system channel.

### 2024-01 — GitHub, Docker, music player beta
- Migrated from Repl.it to GitHub and Dockerized the application.
- Migrated hosting to Microsoft Azure.
- Rewrote `VoiceChannel.py` toward music playback; shipped a beta then lite music
  player with voice-channel recording.

### 2023-12 — Attachments & cogs restructure
- Renamed `SendMessage.py` → `SendFromInput.py`; added single-attachment sending.
- Fixed `Greetings` erroneously DMing bots.
- Migrated `general/` and `administration/` into `cogs/`; renamed `MainBOT.py`
  → `startup.py`.

### 2023-11 — Moderation & OpenAI integration
- Added `LockChannel.py` with antiraid activate/deactivate; fixed slow multi-
  channel lockdowns.
- Integrated the OpenAI API (`ChatGPT.py`); tuned model parameters and moved to
  `gpt-3.5-turbo-1106`; added 15-message conversation history and a `reset`
  command; upgraded the `openai` module 0.27 → 1.0.
- Rewrote `ChangeStatus.py` with full activity-type support.
- Added `ReactingMessages.py` (reaction add/remove/list/clear).
- Renamed env var `TOKEN` → `DISCORD_BOT_TOKEN`.

### 2023-10-03 → 2023-10-29 — Project inception
- Bot created; development started on Replit.
- Added `MessageFiltering` and `Greetings`.
- Migrated from discord.py to Pycord.
- First deployment; added `ban_guild()`.

[Unreleased]: https://github.com/HikariApp/hikari/compare/v3.5.1...HEAD
[3.5.0]: https://github.com/HikariApp/hikari/compare/v3.5.0...v3.5.1
[3.5.0]: https://github.com/HikariApp/hikari/compare/v3.3.0...v3.5.0
[3.3.0]: https://github.com/HikariApp/hikari/compare/v3.2.2...v3.3.0
[3.2.2]: https://github.com/HikariApp/hikari/compare/v3.2.1...v3.2.2
[3.2.1]: https://github.com/HikariApp/hikari/compare/v3.1.7...v3.2.1
[3.1.7]: https://github.com/HikariApp/hikari/compare/v3.1.0...v3.1.7
[3.1.0]: https://github.com/HikariApp/hikari/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/HikariApp/hikari/compare/v2.9.7...v3.0.0
[2.9.7]: https://github.com/HikariApp/hikari/compare/v2.9.3...v2.9.7
[2.9.3]: https://github.com/HikariApp/hikari/compare/v2.8.5...v2.9.3
[2.8.5]: https://github.com/HikariApp/hikari/compare/v2.7.3...v2.8.5
[2.7.3]: https://github.com/HikariApp/hikari/compare/v2.7.0...v2.7.3
[2.7.0]: https://github.com/HikariApp/hikari/compare/v2.6.6...v2.7.0
[2.6.6]: https://github.com/HikariApp/hikari/compare/v2.2.5...v2.6.6
[2.2.5]: https://github.com/HikariApp/hikari/compare/v2.2.0...v2.2.5
[2.2.0]: https://github.com/HikariApp/hikari/compare/v2.1.8...v2.2.0
[2.1.8]: https://github.com/HikariApp/hikari/compare/v2.1.7...v2.1.8
[2.1.7]: https://github.com/HikariApp/hikari/compare/v2.1.5...v2.1.7
[2.1.5]: https://github.com/HikariApp/hikari/compare/v2.1.4...v2.1.5
[2.1.4]: https://github.com/HikariApp/hikari/compare/v2.1.0...v2.1.4
[2.1.0]: https://github.com/HikariApp/hikari/compare/v2.0.6...v2.1.0
[2.0.6]: https://github.com/HikariApp/hikari/compare/v2.0.3...v2.0.6
[2.0.3]: https://github.com/HikariApp/hikari/compare/v2.0.2...v2.0.3
[2.0.2]: https://github.com/HikariApp/hikari/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/HikariApp/hikari/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/HikariApp/hikari/compare/v1.9.4...v2.0.0
[1.9.4]: https://github.com/HikariApp/hikari/compare/v1.9.3...v1.9.4
[1.9.3]: https://github.com/HikariApp/hikari/compare/v1.6.8...v1.9.3
[1.6.8]: https://github.com/HikariApp/hikari/compare/v1.6.1...v1.6.8
[1.6.1]: https://github.com/HikariApp/hikari/compare/v1.5.3...v1.6.1
[1.5.3]: https://github.com/HikariApp/hikari/compare/v1.5.2...v1.5.3
[1.5.2]: https://github.com/HikariApp/hikari/compare/v1.5.1...v1.5.2
[1.5.1]: https://github.com/HikariApp/hikari/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/HikariApp/hikari/compare/v1.4.6...v1.5.0
[1.4.6]: https://github.com/HikariApp/hikari/compare/v1.4.5...v1.4.6
[1.4.5]: https://github.com/HikariApp/hikari/compare/v1.4.4...v1.4.5
[1.4.4]: https://github.com/HikariApp/hikari/compare/v1.4.3...v1.4.4
[1.4.3]: https://github.com/HikariApp/hikari/compare/v1.4.2...v1.4.3
[1.4.2]: https://github.com/HikariApp/hikari/compare/v1.4.1...v1.4.2
[1.4.1]: https://github.com/HikariApp/hikari/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/HikariApp/hikari/compare/v1.3.6...v1.4.0
[1.3.6]: https://github.com/HikariApp/hikari/compare/v1.3.5...v1.3.6
[1.3.5]: https://github.com/HikariApp/hikari/compare/v1.3.4...v1.3.5
[1.3.4]: https://github.com/HikariApp/hikari/compare/v1.3.3...v1.3.4
[1.3.3]: https://github.com/HikariApp/hikari/compare/v1.3.2...v1.3.3
[1.3.2]: https://github.com/HikariApp/hikari/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/HikariApp/hikari/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/HikariApp/hikari/compare/v1.2.9...v1.3.0
[1.2.9]: https://github.com/HikariApp/hikari/compare/v1.2.8...v1.2.9
[1.2.8]: https://github.com/HikariApp/hikari/compare/v1.2.5...v1.2.8
[1.2.5]: https://github.com/HikariApp/hikari/compare/v1.2.2...v1.2.5
[1.2.2]: https://github.com/HikariApp/hikari/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/HikariApp/hikari/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/HikariApp/hikari/compare/v1.1.5...v1.2.0
[1.1.5]: https://github.com/HikariApp/hikari/compare/v1.1.4...v1.1.5
[1.1.4]: https://github.com/HikariApp/hikari/compare/v1.1.0...v1.1.4
[1.1.0]: https://github.com/HikariApp/hikari/compare/v1.0.8...v1.1.0
[1.0.8]: https://github.com/HikariApp/hikari/compare/v1.0.7...v1.0.8
[1.0.7]: https://github.com/HikariApp/hikari/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/HikariApp/hikari/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/HikariApp/hikari/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/HikariApp/hikari/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/HikariApp/hikari/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/HikariApp/hikari/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/HikariApp/hikari/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/HikariApp/hikari/releases/tag/v1.0.0
