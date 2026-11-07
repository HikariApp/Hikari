# Agent Instructions — Hikari

Hikari is a Discord bot built on discord.py, packaged as a uv project. All code lives in the `hikari_bot` package under `src/hikari_bot/`: `startup.py` holds the bot and `main()`, cogs live under `bot/` and shared code under `helpers/` (paths below are relative to `src/hikari_bot/`). Run it with `uv run hikari-bot` or `python -m hikari_bot`.

Internal imports are absolute and go through the package, e.g. `from hikari_bot.helpers.respondembed import respond_embed` and `from hikari_bot.startup import MyBot`.

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

`helpers/extensionshandler.py` auto-discovers every `.py` file under `bot/{general,moderation,owneronly,extensions}`, relative to the installed package rather than the working directory. It skips files whose names start with `_`, which are helper modules.

Extension names are relative to the package (`bot.general.poll`, not `hikari_bot.bot.general.poll`), which keeps the owner `load`/`unload`/`reload` arguments and `DISABLE_*` flags unchanged from before packaging. Always pass names through `to_module_path()` before calling `load_extension`/`unload_extension`/`reload_extension`.

An extension can be disabled with the env var `DISABLE_<DOTTED_PATH_UPPERCASED_WITH_UNDERSCORES>`, e.g. `DISABLE_BOT_EXTENSIONS_CHATBOT_CHATBOT`. Renaming an extension file or folder therefore changes its disable flag and its `load`/`unload`/`reload` path.

## ChatBot extension

The ChatBot lives in `bot/extensions/chatbot/`, like the music player and voice recorder. It talks to Claude through the official `anthropic` SDK, either directly (`ANTHROPIC_API_KEY`, which takes priority) or through Poe's Anthropic-compatible API at `https://api.poe.com` (`POE_API_KEY`, billed to the Poe subscription's points, kept as a backup). `PROVIDERS` in `_claudeservice.py` holds each provider's base URL, key and model names. It is disabled by default in `example.env` (`DISABLE_BOT_EXTENSIONS_CHATBOT_CHATBOT=1`) because it needs one of those keys.

`chatbot.py` holds only the cog: commands, listeners and Discord replies. Everything else lives in internal helpers next to it:

- `_claudeservice.py`: Claude API calls, model tiers, the system prompt, and how user turns and attachments are built.
- `_chatbotrepository.py`: MongoDB access for conversations and access tiers.
- `_chatbotui.py`: the `/chatbot` modal, splitting replies into Discord-sized messages, and error embeds.

Keep new API or database code in the helpers, not in the cog.

- `/chatbot` answers the first message, then opens a thread on the reply. Every later message in that thread is a turn of the same conversation.
- The system prompt (`SYSTEM_PROMPT`) has two parts: personality and style defaults (the cat persona, language, length), which thread instructions or a plain request in the conversation may change, and rules that always apply (name labels, Discord formatting, no `@everyone`/`@here`, prompt privacy), which nothing may change. Keep anything security-relevant in the second part.
- The `/chatbot` modal has an optional instructions box. `clean_instructions()` strips tags that could close the block early and caps the length, and the result is stored as `instructions` on the conversation and appended to the system prompt inside `<thread_instructions>` tags, framed as user-written text with no more authority than a user message. Instructions are fixed for the life of the thread, which keeps the system prompt identical on every turn.
- Conversations live in the `chatbot.conversations` MongoDB collection, one document per thread (`_id` is the thread ID). `messages` is the Claude message history and is only ever appended to. Never edit, reorder or trim earlier turns: that breaks prompt caching and invalidates the stored thinking blocks.
- Access tiers come from `chatbot.user_access` / `chatbot.server_access` (`trial`, `basic`, `premium`) and map to the same models on both providers (Opus 4.7, Sonnet 4.6, Haiku 4.5), spelled per provider in `PROVIDERS` (`claude-sonnet-4-6` on Anthropic, `claude-sonnet-4.6` on Poe). Keep both providers on the same models, so a conversation can continue after switching. A conversation keeps the tier it started with. Haiku 4.5 supports neither adaptive thinking nor effort, so its tier sends neither (`TIER_EFFORT`).
- Poe only offers `/v1/messages` (its `/v1/files` returns 404), so neither provider uses the Files API. Instead, attachment bytes are stored once in the `chatbot.attachments` GridFS bucket, and the history keeps only `{"type": "stored_attachment", "attachment_id": ...}` references. Before each request, `ClaudeService` loads them through the repository and swaps each reference for inline content (base64 images and PDFs, plain-text documents); the stored history is never changed. Older conversations that hold inline base64 keep working as they are. `/resetchatbot` deletes a conversation's attachments with it, and a turn that fails deletes the attachments it stored. Attachments are still resent on every turn, so the caps in `_claudeservice.py` (5 MB per file, 20 MB per conversation, tracked in `attachment_bytes`) keep requests within the API's limits: a 6 MB base64 image and a 35 MB request were both accepted through Poe.
- Claude can search the web with Anthropic's server-side `web_search_20250305` tool (`WEB_SEARCH_TOOL`), which Poe passes through; it was tested on Sonnet 4.6 and Haiku 4.5. `WEB_SEARCH_MAX_USES` caps searches per message (currently 5; 0 turns search off). Replies are streamed: when Claude starts a search, the text it wrote before it is passed to the cog's `on_part` callback and posted at once, with the typing indicator kept up while it searches. `_reply_parts()` splits the finished reply the same way, and `ClaudeReply.unsent_parts` holds whatever wasn't posted yet. A search costs roughly 20–40× the points of a plain message on Poe.
- Each user message's label carries its send time in UTC (`[Name (<@id>) · 2026-11-07 18:48 UTC]`), so Claude knows the current date for searches. The time goes in the label rather than the system prompt so the prompt stays identical on every turn.
- A reply that searched is stored as its text alone, without the raw search results (tens of KB). The evidence is kept as a `[Search note: ...]` text block, with the queries and cited passages, appended to the user's message in the history. Without it, Claude later sees an answer with no sign of a search, assumes it made the answer up, and searches again.
- Only use features both providers support. Don't add Anthropic beta headers or features Poe may not pass through without testing them against Poe first.
- The old OpenAI collections (`assistants`, `discord_channels`, `files`) are no longer used.
