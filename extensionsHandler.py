import os
import asyncio

extensions_folders = ['general', 'moderation', 'ownerOnly', 'extensions', 'errorhandling', 'configs']

# Getting all extensions from the extensions folders
# UPDATE 17-10-2025: Rewrited with asyncio.to_thread and os.walk to support subdirectories, and you can name a file starts with `_` to prevent loading
async def getAllExtensions():
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Getting all extensions from the extensions folders ends with `.py` and not starts with `_`, see Note below for more details.

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
        folder_path = f"./{folder}"
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
                    
                    # Conditional loading based on environment variables
                    if extension == "general.ChatGPT" and os.getenv("ENABLE_AI") == "False":
                        continue

                    if extension == "extensions.MusicPlayer.Music" and os.getenv("ENABLE_MUSIC") == "False":
                        continue

                    extensions.append(extension)

    return extensions

