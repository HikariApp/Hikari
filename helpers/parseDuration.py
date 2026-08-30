"""
The MIT License (MIT)

Copyright (c) 2026 Hoshino Yuki

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

# SPDX-License-Identifier: MIT

import re
from typing import Union

# Convert time string to seconds and detailed duration breakdown
def parseDuration(durationStr: str) -> Union[dict, str]:
    """
    Converts a duration string into total seconds and provides a detailed breakdown of the duration.

    Parameters
    ----------
    durationStr : str
        The duration string to be parsed. It can contain multiple time units (e.g., "1h30m", "2d5h", "3w2d4h").
    
    Returns
    -------
    None
        If the input format is invalid, returns None.
    dict
        A dictionary containing the total seconds and a breakdown of the duration into years, months, weeks
    """

    units = {
        "s": 1,        # seconds
        "m": 60,       # minutes
        "h": 3600,     # hours
        "d": 86400,    # days
        "w": 604800,   # weeks
        "mo": 2592000, # months (approximate)
        "y": 31536000  # years (approximate)
    }

    matches = re.findall(r"(\d+)(mo|[smhdwy])", durationStr)
    
    if not matches:    # If no valid matches are found, return None to indicate an improper format
        return

    totalSeconds = 0
    durationBreakdown = {
        "years": 0,
        "months": 0,
        "weeks": 0,
        "days": 0,
        "hours": 0,
        "minutes": 0,
        "seconds": 0
    }

    for amount, unit in matches:
    
        if unit in units:
            totalSeconds += int(amount) * units[unit]
            durationBreakdown[{
                "y": "years",
                "mo": "months",
                "w": "weeks",
                "d": "days",
                "h": "hours",
                "m": "minutes",
                "s": "seconds"
            }[unit]] += int(amount)

    durationBreakdown["total_seconds"] = totalSeconds
    return durationBreakdown
