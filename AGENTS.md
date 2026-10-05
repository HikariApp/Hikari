# Agent Instructions — Hikari

Hikari is a Discord bot built on discord.py (`startup.py` is the entry point; cogs live under `bot/`, shared code under `helpers/`).

## Naming convention: snake_case

The project's own code used to be camelCase, to tell it apart from discord.py code. It has been converted to snake_case and new code must follow suit.

- Functions, methods, variables, attributes and parameters use `snake_case`.
- Classes stay `PascalCase` and constants stay `UPPER_SNAKE_CASE`, as in PEP 8.
- Acronyms collapse to one lowercase word: `avatar_url`, `get_mongo_cluster_db`, `convert_to_gib`.
- Helper module file names are all lowercase with no separators between words:
  - Shared helpers in `helpers/`: `errorhandling.py`, `networkinfo.py`, `respondembed.py`.
  - Internal helpers inside an extension keep the leading `_`: `_betterqueue.py`, `_betterplayer.py`, `_playerhelper.py`.
  - So the module is `helpers.respondembed` while the function inside it stays `respond_embed`.
  - Deliberate exceptions, keep as-is: `musicplayer/commands/_music_general.py` and `musicplayer/commands/_music_queuesystem.py`.
- Cog (extension) files are all lowercase too: `bot/general/voicechannel.py`, `bot/moderation/getbannedlist.py`, `bot/owneronly/owneronly.py`. The cog classes inside stay `PascalCase` (`VoiceChannel`, `GetBannedList`).
- When renaming, update every reference in the same change: imports, keyword-argument call sites, attribute access across files, and names inside strings, such as `getattr(ctx, "_error_handled", ...)` and `getattr(self.queue, "_playback_history", ...)`.
- Before renaming, check that the snake_case name is not already taken in the same scope. Also check that it does not shadow an attribute of the parent class (discord.py `Bot`/`Cog`, lava_lyra `Player`/`Queue`).
- Do not rename user-facing slash/hybrid command names or parameters, Discord-visible strings, MongoDB field names or environment variable names as part of a naming cleanup unless asked. These are external contracts.

## Line endings: LF only

The bot runs on Linux via Docker Compose, so every file uses LF line endings, never CRLF. `.gitattributes` (`* text=auto eol=lf`) enforces this on checkout even on Windows with `core.autocrlf=true`. When editing on Windows, make sure your tools write LF. Git Bash `sed -i` and Python `read_text`/`write_text` round-trips can silently change line endings, so check the raw bytes after bulk edits.

## License headers

Some files start with an MIT license header block, either a `"""..."""` docstring or `#` comments, e.g. `helpers/*.py` and the `_`-prefixed musicplayer and voicerecorder modules.

- Never modify, reformat, move or remove a license header block unless explicitly asked.
- Do not add license headers to new files. Provide new code without a header; the maintainer adds headers themselves when needed.

## Extension loading

`helpers/extensionshandler.py` auto-discovers every `.py` file under `bot/{general,moderation,owneronly,extensions}`. It skips files whose names start with `_`, which are helper modules.

An extension can be disabled with the env var `DISABLE_<DOTTED_PATH_UPPERCASED_WITH_UNDERSCORES>`, e.g. `DISABLE_BOT_GENERAL_CHATBOT`. Renaming an extension file or folder therefore changes its disable flag and its `load`/`unload`/`reload` path.
