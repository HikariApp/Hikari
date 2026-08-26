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
    _playbackHistory : List[lava_lyra.Track]
        A list-based queue that maintains the full history of tracks played.
    _currentIndex : Optional[int]
        The index of the current track in `_playbackHistory`. None means not initialized (before-first).

    Methods
    -------
    get()
        Retrieves the next track from the queue and updates `_currentIndex` accordingly.
    copy()
        Creates a copy of the current queue including all its members.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._playbackHistory: List[Track] = []    # Full list of tracks including played ones (history-like; we never remove from this)
        self._currentIndex: Optional[int] = None    # Position in the queue, None means before-first
        self._qEnd: bool = False    # To track if the queue has reached the end



    def __getitem__(self, key):  # type: ignore[override]
        if isinstance(key, slice):
            return self._queue[key]  # returns List[lava_lyra.Track]
        return super().__getitem__(key)


    # Record successful enqueues into _playbackHistory
    def put(self, item: Track) -> None:  # type: ignore[override]
        super().put(item)
        self._playbackHistory.append(item)


    def extend(self, iterable: Iterable[Track], *, atomic: bool = True) -> None:  # type: ignore[override]
        # super().extend will call self.put per item, which already appends to _playbackHistory
        super().extend(iterable, atomic=atomic)


    def put_at_index(self, index: int, item: Track) -> None:  # type: ignore[override]
        super().put_at_index(index, item)
        # Keep history with positional intent: insert at that index
        self._playbackHistory.insert(index, item)
        # If inserted before or at the current item, bump the pointer to keep pointing at the same item
        if self._currentIndex >= 0 and index <= self._currentIndex:
            self._currentIndex += 1


    def put_at_front(self, item: Track) -> None:  # type: ignore[override]
        super().put_at_front(item)
        self._playbackHistory.insert(0, item)
        if self._currentIndex >= 0:
            self._currentIndex += 1


    def get(self) -> Track:  # type: ignore[override]
        """
        Return next immediately available item in queue if any.

        This also updates `_currentIndex` to point to the returned item in `_playbackHistory`.

        If there exists any duplicated tracks in the queue, `_currentIndex` will point to the first occurrence after the previous `_currentIndex`.

        `_playbackHistory` will not be modified after `Queue.pop()`, so the full history will be preserved.

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
            wrapped = not self._queue and bool(self._playbackHistory)
            if wrapped:
                self._queue = self._playbackHistory.copy()

            item = self._get()
            self._current_item = item

            if wrapped or self._currentIndex is None:
                self._currentIndex = 0
            else:
                self._currentIndex = (self._currentIndex + 1) % len(self._playbackHistory)

            return item

        else:
            item = super().get()

        #
        # Overrides the default behavior of lava_lyra.Queue.get() to update _currentIndex
        #
        
        originalIndex = self._currentIndex if self._currentIndex is not None else 0

        try:
            self._currentIndex = self._playbackHistory.index(item, originalIndex)

        except ValueError as e:
            # This should never happen, but just in case
            raise e

        # If the item was found before originalIndex
        if originalIndex > self._currentIndex:
            try:
                # Checking if any duplicates exist after originalIndex
                self._currentIndex = self._playbackHistory.index(item, originalIndex + 1)

            except ValueError:
                # Don't worry, this just means no duplicates found after originalIndex, not an error
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

        Same as `lava_lyra.Queue.copy()` but also maintains the state of `_playbackHistory` and `_currentIndex`.
        
        Returns
        -------
        BetterQueue
            A new instance of `BetterQueue` with the same contents and state as the original.
        """

        # Preserve constructor options (max_size, overflow)
        newQueue: BetterQueue = self.__class__(max_size=self.max_size, overflow=self._overflow)  # type: ignore[arg-type]

        # Copy runtime queue contents (shallow)
        newQueue._queue = copy(self._queue)

        # Copy BetterQueue extras
        newQueue._playbackHistory = copy(self._playbackHistory)
        newQueue._currentIndex = copy(self._currentIndex)

        return newQueue


    def remove(self, item):
        """
        Remove the first occurrence of item.
        
        This also removes the item from `_playbackHistory`.

        Parameters
        ----------
        item : lava_lyra.Track
            The track to remove from the queue.

        Returns
        -------
        None
        """
    
        super().remove(item)
        self._playbackHistory.remove(item)


    def clear(self) -> None:
        """
        Remove all items from the queue.

        This also resets our `_playbackHistory` and resets `_currentIndex` to None (before-first).

        Returns
        -------
        None
        """

        super().clear()
        self._playbackHistory.clear()
        self._currentIndex = None  # Reset to before-first


    @property
    def playbackHistory(self) -> List[Track]:
        """
        Returns the full playback history as a list.

        Returns
        -------
        List[lava_lyra.Track]
            A list of tracks in the playback history.
        """

        return self._playbackHistory


    @property
    def historyIsEmpty(self) -> bool:
        """
        Check if the playback history is empty.

        Returns
        -------
        bool
            True if the playback history is empty, False otherwise.
        """

        return len(self._playbackHistory) == 0


    @property
    def historySize(self) -> int:
        """
        Returns the size of the playback history.

        Returns
        -------
        int
            The number of tracks in the playback history.
        """

        return len(self._playbackHistory)


    @property
    def currentTrackIndex(self) -> int | None:
        """
        Returns current track index.

        Similar to `Queue.find_position()` but works with our `_playbackHistory` and `_currentIndex`.

        It is highly recommended to use this property instead of `Queue.find_position()` as the latter
        
        does not account for tracks that have already been played and removed from the queue.

        Returns
        -------
        int
            Returns the current track index if `_currentIndex` is a valid non-negative integer.

        None
            The `_currentIndex` has not been initialized (before-first).
        """

        return self._currentIndex if self._currentIndex is not None and self._currentIndex >= 0 else None


    @currentTrackIndex.setter
    def currentTrackIndex(self, value: int | None) -> None:
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
            self._currentIndex = None
            return

        self._currentIndex = int(value)


    @property
    def isAtHistoryEnd(self) -> bool:
        """
        Check if the queue has reached the end.

        This is useful for determining if playback has finished all tracks in the queue.

        Returns
        -------
        bool
            `True` if the queue has reached the end, `False` otherwise.
        """

        return bool(self._qEnd)

    
    @isAtHistoryEnd.setter
    def isAtHistoryEnd(self, value: bool) -> None:
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

        self._qEnd = value

    
    @property
    def isAtHistoryStart(self) -> bool:
        """
        Check if the queue has reached the beginning.

        Examaining only `_currentIndex` is not sufficient, as sometimes the player has a single track only, and `_currentIndex` will still be 0 even after the track has been played.
        
        This will be `True` if `_currentIndex` is 0 and the queue has not reached the end.

        Returns
        -------
        bool
            `True` if the queue has reached the beginning, `False` otherwise.
        """

        return (self._currentIndex == 0 and self._qEnd is False)


