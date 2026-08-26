"""
The MIT License (MIT)

Copyright (c) 2024-2026 Hoshino Yuki  
Copyright (c) 2026 Hikari

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

import os
import asyncio

bot_folder = "./bot"
extensions_folders = ['general', 'moderation', 'ownerOnly', 'extensions']

# Getting all extensions from the extensions folders
async def getAllExtensions():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Getting all extensions from the extensions folders ends with `.py` and not starts with `_` inside the `./bot/` directory, see Note below for more details.

    Note
    ----------
    This function has been rewrited, and now uses `asyncio.to_thread` to run blocking I/O operations in a separate thread, preventing the main event loop from being blocked.

    Since the latest rewrite, this function is now fully asynchronous and non-blocking.

    And you can now add subdirectories in the extensions folders, and the function will find them all.

    Also, you can named your files starts with `_` to prevent them from being loaded as extensions, which is useful for utility modules.

    """
    global extensions_folders
    extensions = []

    # Use asyncio.to_thread to perform blocking I/O in a separate thread
    for folder in extensions_folders:
        folder_path = f"{bot_folder}/{folder}"
        if not os.path.exists(folder_path):
            continue

        # Use os.walk to recursively traverse directories
        walk_result = await asyncio.to_thread(list, os.walk(folder_path))
        
        for root, _, files in walk_result:
            for filename in files:
                if filename.endswith('.py') and not filename.startswith('_'):
                    # Convert file path to discord.py Cog format
                    relative_path = os.path.relpath(os.path.join(root, filename), ".").replace(os.sep, ".")
                    extension = relative_path[:-3]  # Remove .py extension
                    
                    # Check if the extension was disabled by environment variable
                    if bool(os.getenv(extension)):
                        continue

                    extensions.append(extension)

    return extensions
