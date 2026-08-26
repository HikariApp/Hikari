# The MIT License (MIT)
#
# Copyright (c) 2024–2026 Hoshino Yuki
# Copyright (c) 2026 Hikari
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
#
# SPDX-License-Identifier: MIT

"""
Extension discovery for Hikari.

Convention
----------
Files under `./bot` whose names start with `_` are treated as cog helpers
and are never loaded as extensions (note this also skips `__init__.py`).
Only `*.py` files without a leading underscore are returned as loadable
discord.py extension paths.

A discovered extension can be disabled via an environment variable. The module
path is normalized to an UPPER_SNAKE flag prefixed with `DISABLE_` so it is
actually settable from a shell / .env file, e.g.::

    bot.general.Poll  ->  DISABLE_BOT_GENERAL_POLL=1
"""

import os
import asyncio
import logging

logger = logging.getLogger(__name__)

BOT_FOLDER = "./bot"
EXTENSIONS_FOLDERS = ["general", "moderation", "ownerOnly", "extensions"]
DISABLE_PREFIX = "DISABLE_"
ENV_TRUTHY_VALUES = {"1", "true", "yes"}


def isDisabled(extension: str) -> bool:
    """
    Check if the given extension is disabled via an environment variable.

    Parameters
    ----------
    extension : str
        The dotted import path of the extension, e.g. `bot.general.Mute`.

    Returns
    -------
    bool
        True if the extension is disabled, False otherwise.
    """
    flag = DISABLE_PREFIX + extension.upper().replace(".", "_")
    value = os.getenv(flag)
    return value is not None and value.strip().lower() in ENV_TRUTHY_VALUES


async def getAllExtensions() -> list[str]:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Get all loadable extensions in the bot's extension folders.

    Recursively discovers every `*.py` file inside the configured extension
    folders that does **not** start with `_`, returning their dotted import
    paths for `bot.load_extension`. Blocking I/O runs in a worker thread via
    `asyncio.to_thread` so the event loop is never blocked.

    Returns
    -------
    list[str]
        A list of dotted import paths for all loadable extensions.

    
    """

    extensions: list[str] = []

    for folder in EXTENSIONS_FOLDERS:
        folder_path = os.path.join(BOT_FOLDER, folder)

        if not os.path.isdir(folder_path):
            logger.warning("Extension folder missing, skipping: %s", folder_path)
            continue

        try:
            walk_result = await asyncio.to_thread(list, os.walk(folder_path))

        except OSError as e:
            logger.error("Failed to walk %s: %s", folder_path, e)
            continue

        for root, _, files in walk_result:    # _ stands for "dirs" which we don't need to use
            for filename in files:
                if not filename.endswith(".py"):
                    continue

                if filename.startswith("_"):  # this would skip all helpers (and __init__.py)
                    continue

                relative_path = os.path.relpath(
                    os.path.join(root, filename), "."
                ).replace(os.sep, ".")
                extension = relative_path[:-3]  # strip ".py"

                if isDisabled(extension):
                    logger.info("Extension disabled via env, skipping: %s", extension)
                    continue

                extensions.append(extension)

    if not extensions:
        logger.warning("No extensions discovered — is ./bot laid out as expected?")

    logger.info("Discovered %d extension(s).", len(extensions))
    return extensions

