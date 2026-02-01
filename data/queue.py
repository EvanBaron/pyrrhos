from collections import deque
from data.track import Track
from data.exceptions import QueueError


class MusicQueue:
    """Manages a queue of music tracks for a guild."""

    def __init__(self):
        self._queue: deque[Track] = deque()
        self._history: deque[Track] = deque(maxlen=10)
        self._loop: bool = False
        self._loop_queue: bool = False

    def __len__(self) -> int:
        """Return the number of tracks in queue."""

        return len(self._queue)

    def __bool__(self) -> bool:
        """Return True if queue is not empty."""

        return len(self._queue) > 0

    def __iter__(self):
        """Iterate over tracks in queue."""

        return iter(self._queue)

    def __getitem__(self, index: int) -> Track:
        """Get track at index."""

        if index < 0 or index >= len(self._queue):
            raise QueueError(f"Index {index} out of range")
        return self._queue[index]

    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""

        return len(self._queue) == 0

    @property
    def loop(self) -> bool:
        """Get loop status."""

        return self._loop

    @loop.setter
    def loop(self, value: bool):
        """Set loop status."""

        self._loop = value

    @property
    def loop_queue(self) -> bool:
        """Get queue loop status."""

        return self._loop_queue

    @loop_queue.setter
    def loop_queue(self, value: bool):
        """Set queue loop status."""

        self._loop_queue = value

    @property
    def history(self) -> list[Track]:
        """Get recently played tracks."""

        return list(self._history)

    def add(self, track: Track) -> int:
        """
        Add a track to the queue.

        Args:
            track: Track to add

        Returns:
            Position in queue (0-indexed)
        """

        self._queue.append(track)

        return len(self._queue) - 1

    def add_next(self, track: Track):
        """
        Add a track to play next (front of queue).

        Args:
            track: Track to add
        """

        self._queue.appendleft(track)

    def get_next(self) -> Track | None:
        """
        Get the next track from queue.

        Returns:
            Next track or None if queue is empty
        """

        if self.is_empty:
            return None

        track = self._queue.popleft()
        self._history.append(track)

        if self._loop_queue:
            self._queue.append(track)

        return track

    def peek(self) -> Track | None:
        """
        Peek at the next track without removing it.

        Returns:
            Next track or None if queue is empty
        """

        if self.is_empty:
            return None

        return self._queue[0]

    def remove(self, index: int) -> Track:
        """
        Remove a track at a specific index.

        Args:
            index: Index of track to remove

        Returns:
            Removed track

        Raises:
            QueueError: If index is out of range
        """

        if index < 0 or index >= len(self._queue):
            raise QueueError(f"Index {index} out of range")

        track = self._queue[index]
        del self._queue[index]
        return track

    def clear(self):
        """Clear all tracks from the queue."""
        self._queue.clear()

    def shuffle(self):
        """Shuffle the queue randomly."""
        import random

        tracks = list(self._queue)
        random.shuffle(tracks)
        self._queue = deque(tracks)

    def move(self, from_index: int, to_index: int):
        """
        Move a track from one position to another.

        Args:
            from_index: Current index of track
            to_index: Target index for track

        Raises:
            QueueError: If indices are out of range
        """

        if from_index < 0 or from_index >= len(self._queue):
            raise QueueError(f"Source index {from_index} out of range")
        if to_index < 0 or to_index >= len(self._queue):
            raise QueueError(f"Target index {to_index} out of range")

        track = self._queue[from_index]
        del self._queue[from_index]
        self._queue.insert(to_index, track)

    def get_total_duration(self) -> int:
        """
        Get total duration of all tracks in queue.

        Returns:
            Total duration in seconds
        """

        return sum(track.duration for track in self._queue)

    def to_list(self) -> list[Track]:
        """
        Convert queue to a list.

        Returns:
            List of tracks in queue
        """

        return list(self._queue)
