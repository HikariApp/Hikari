"""
The MIT License (MIT)

Copyright (c) 2025 Hoshino Yuki

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

import logging
from copy import copy
from typing import List, Optional, Iterable
from lava_lyra import LoopMode, Queue, Track

logger = logging.getLogger(__name__)

class BetterQueue(Queue):
    """
    A custom queue class that extends `lava_lyra.Queue` to include advanced queue management and history tracking.

    This allows us to maintain a full history of tracks played, indexing and slicing.

    Attributes
    ----------
    _playback_history : List[lava_lyra.Track]
        A list-based queue that maintains the full history of tracks played.
    _current_index : Optional[int]
        The index of the current track in `_playback_history`. None means not initialized (before-first).

    Methods
    -------
    get()
        Retrieves the next track from the queue and updates `_current_index` accordingly.
    copy()
        Creates a copy of the current queue including all its members.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._playback_history: List[Track] = []    # Full list of tracks including played ones (history-like; we never remove from this)
        self._current_index: Optional[int] = None    # Position in the queue, None means before-first
        self._q_end: bool = False    # To track if the queue has reached the end



    def __getitem__(self, key):  # type: ignore[override]
        if isinstance(key, slice):
            return self._queue[key]  # returns List[lava_lyra.Track]
        return super().__getitem__(key)


    # Record successful enqueues into _playback_history
    def put(self, item: Track) -> None:  # type: ignore[override]
        super().put(item)
        self._playback_history.append(item)


    def extend(self, iterable: Iterable[Track], *, atomic: bool = True) -> None:  # type: ignore[override]
        # super().extend will call self.put per item, which already appends to _playback_history
        super().extend(iterable, atomic=atomic)


    def put_at_index(self, index: int, item: Track) -> None:  # type: ignore[override]
        super().put_at_index(index, item)
        # Keep history with positional intent: insert at that index
        self._playback_history.insert(index, item)
        # If inserted before or at the current item, bump the pointer to keep pointing at the same item
        if self._current_index >= 0 and index <= self._current_index:
            self._current_index += 1


    def put_at_front(self, item: Track) -> None:  # type: ignore[override]
        super().put_at_front(item)
        self._playback_history.insert(0, item)
        if self._current_index >= 0:
            self._current_index += 1


    def get(self) -> Track:  # type: ignore[override]
        """
        Return next immediately available item in queue if any.

        This also updates `_current_index` to point to the returned item in `_playback_history`.

        If there exists any duplicated tracks in the queue, `_current_index` will point to the first occurrence after the previous `_current_index`.

        `_playback_history` will not be modified after `Queue.pop()`, so the full history will be preserved.

        However, if the queue is empty, this will raise `lava_lyra.QueueEmpty` as usual.

        Returns
        -------
        lava_lyra.Track
            The next track in the queue.

        Raises 
        ------
        lava_lyra.QueueEmpty
            Raised if no items in queue.
        """

        if self.loop_mode == LoopMode.QUEUE:
            wrapped = not self._queue and bool(self._playback_history)
            if wrapped:
                self._queue = self._playback_history.copy()

            item = self._get()
            self._current_item = item

            if wrapped or self._current_index is None:
                self._current_index = 0
            else:
                self._current_index = (self._current_index + 1) % len(self._playback_history)

            return item

        else:
            item = super().get()

        #
        # Overrides the default behavior of lava_lyra.Queue.get() to update _current_index
        #

        original_index = self._current_index if self._current_index is not None else 0

        try:
            self._current_index = self._playback_history.index(item, original_index)

        except ValueError as e:
            # This should never happen, but just in case
            raise e

        # If the item was found before original_index
        if original_index > self._current_index:
            try:
                # Checking if any duplicates exist after original_index
                self._current_index = self._playback_history.index(item, original_index + 1)

            except ValueError:
                # Don't worry, this just means no duplicates found after original_index, not an error
                pass

        return item


    def set_loop_mode(self, mode: LoopMode) -> None:  # type: ignore[override]
        if mode == LoopMode.QUEUE:
            self._loop_mode = mode
            return

        super().set_loop_mode(mode)


    def disable_loop(self) -> None:  # type: ignore[override]
        if self.loop_mode == LoopMode.QUEUE:
            self._loop_mode = None
            return

        super().disable_loop()


    def copy(self) -> "BetterQueue":  # type: ignore[override]
        """
        Create a copy of the current queue including all it's members.

        Same as `lava_lyra.Queue.copy()` but also maintains the state of `_playback_history` and `_current_index`.

        Returns
        -------
        BetterQueue
            A new instance of `BetterQueue` with the same contents and state as the original.
        """

        # Preserve constructor options (max_size, overflow)
        new_queue: BetterQueue = self.__class__(max_size=self.max_size, overflow=self._overflow)  # type: ignore[arg-type]

        # Copy runtime queue contents (shallow)
        new_queue._queue = copy(self._queue)

        # Copy BetterQueue extras
        new_queue._playback_history = copy(self._playback_history)
        new_queue._current_index = copy(self._current_index)

        return new_queue


    def remove(self, item):
        """
        Remove the first occurrence of item.

        This also removes the item from `_playback_history`.

        Parameters
        ----------
        item : lava_lyra.Track
            The track to remove from the queue.

        Returns
        -------
        None
        """

        super().remove(item)
        self._playback_history.remove(item)


    def clear(self) -> None:
        """
        Remove all items from the queue.

        This also resets our `_playback_history` and resets `_current_index` to None (before-first).

        Returns
        -------
        None
        """

        super().clear()
        self._playback_history.clear()
        self._current_index = None  # Reset to before-first


    @property
    def playback_history(self) -> List[Track]:
        """
        Returns the full playback history as a list.

        Returns
        -------
        List[lava_lyra.Track]
            A list of tracks in the playback history.
        """

        return self._playback_history


    @property
    def history_is_empty(self) -> bool:
        """
        Check if the playback history is empty.

        Returns
        -------
        bool
            True if the playback history is empty, False otherwise.
        """

        return len(self._playback_history) == 0


    @property
    def history_size(self) -> int:
        """
        Returns the size of the playback history.

        Returns
        -------
        int
            The number of tracks in the playback history.
        """

        return len(self._playback_history)


    @property
    def current_track_index(self) -> int | None:
        """
        Returns current track index.

        Similar to `Queue.find_position()` but works with our `_playback_history` and `_current_index`.

        It is highly recommended to use this property instead of `Queue.find_position()` as the latter

        does not account for tracks that have already been played and removed from the queue.

        Returns
        -------
        int
            Returns the current track index if `_current_index` is a valid non-negative integer.

        None
            The `_current_index` has not been initialized (before-first).
        """

        return self._current_index if self._current_index is not None and self._current_index >= 0 else None


    @current_track_index.setter
    def current_track_index(self, value: int | None) -> None:
        """
        Set current track index.

        Parameters
        ----------
        value : int | None
            The new current track index. Use None to reset before-first state.

        Returns
        -------
        None
        """

        if value is None:
            self._current_index = None
            return

        self._current_index = int(value)


    @property
    def is_at_history_end(self) -> bool:
        """
        Check if the queue has reached the end.

        This is useful for determining if playback has finished all tracks in the queue.

        Returns
        -------
        bool
            `True` if the queue has reached the end, `False` otherwise.
        """

        return bool(self._q_end)


    @is_at_history_end.setter
    def is_at_history_end(self, value: bool) -> None:
        """
        Set the end-of-queue status.

        This can be used to manually set the end-of-queue status, which might be useful in certain scenarios.

        Parameters
        ----------
        value : bool
            The new end-of-queue status.

        Returns
        -------
        None
        """

        self._q_end = value


    @property
    def is_at_history_start(self) -> bool:
        """
        Check if the queue has reached the beginning.

        Examaining only `_current_index` is not sufficient, as sometimes the player has a single track only, and `_current_index` will still be 0 even after the track has been played.

        This will be `True` if `_current_index` is 0 and the queue has not reached the end.

        Returns
        -------
        bool
            `True` if the queue has reached the beginning, `False` otherwise.
        """

        return (self._current_index == 0 and self._q_end is False)

