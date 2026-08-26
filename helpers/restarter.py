"""
The MIT License (MIT)

Copyright (c) 2023-2026 Hoshino Yuki  
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
import sys
import time
import logging

logger = logging.getLogger(__name__)


class Restarter:
    """
    A utility class to manage restart requests for the application.

    This class allows you to request a restart of the application,
    specifying a reason and an optional delay before the restart is performed.
    It ensures that only the first restart request is honored,
    ignoring any subsequent requests.

    Support both command invokes from `discord.py` (!restart)
    and triggers from some of the exceptions (e.g. HTTP 429).

    Attributes
    ----------
    requested : bool
        Check if a restart has been requested (read-only property).

    Methods
    -------
    request(reason, delay=0.0)
        Request a restart with a specified reason and optional delay.
    perform()
        Perform the restart if one has been requested.

    Notes
    -----
    Please be aware that you should request a restart first before closing the bot,
    otherwise the restart will not be performed.
    """


    def __init__(self) -> None:
        self._requested = False
        self._delay = 0.0
        self._reason = None


    def request(self, reason: str, delay: float = 0.0) -> None:
        """
        Request a restart.
        
        Note that the first request wins while subsequent requests are ignored.

        Parameters
        ----------
        reason : str
            The reason for the restart request. This will be logged for informational purposes.
        delay : float
            The delay in seconds before the restart is performed. Defaults to 0.0 if unspecified (no delay).

        Returns
        ----------
        None
        """

        if self._requested:
            # First request wins; ignore repeats (e.g. spammed !restart).
            logger.debug("Restart already requested (%s); ignoring '%s'.", self._reason, reason)
            return

        # Set the restart request state and log the request.
        self._requested = True
        self._delay = delay
        self._reason = reason
        logger.info("Restart requested: %s (delay=%ss).", reason, delay)


    @property
    def requested(self) -> bool:
        """
        Check if a restart has been requested.

        Returns
        -------
        bool
            True if a restart has been requested, False otherwise.
        """

        return self._requested

    
    def perform(self) -> None:
        """
        Perform the restart if one has been requested.

        This would replace the current process with a new instance of the same program
        by utilizing `os.execv`.

        If no restart has been requested, this method has nothing to do at all.

        Returns
        -------
        None

        Notes
        -----
        Do not call this method directly unless you have requested 
        a restart first by calling `request()`, otherwise it would be
        caught by the safety guard and do nothing.
        """
        
        if not self._requested:
            return    # No restart requested; nothing to do.
        
        if self._delay:
            logger.info("Restarting in %s seconds (%s)...", self._delay, self._reason)
            time.sleep(self._delay)

        # Re-execute the current process with the same command-line arguments.
        logger.info("Re-executing process (%s).", self._reason)
        os.execv(sys.executable, [sys.executable] + sys.argv)


restarter = Restarter()
"""
A singleton instance of the `Restarter` class. Can be used throughout the application to manage restart requests.
"""

