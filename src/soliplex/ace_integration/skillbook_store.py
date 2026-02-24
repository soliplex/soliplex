import pathlib
import threading

from ace import Skillbook


class SkillbookStore:
    """Per-room Skillbook persistence.

    Manages Skillbook instances in memory, keyed by room_id.
    Persistence path: ``{base_path}/ace/{room_id}/skillbook.json``
    """

    def __init__(self, base_path: pathlib.Path):
        self._base_path = base_path
        self._skillbooks: dict[str, Skillbook] = {}
        self._lock = threading.Lock()

    def _skillbook_path(self, room_id: str) -> pathlib.Path:
        return self._base_path / "ace" / room_id / "skillbook.json"

    def get_for_room(self, room_id: str) -> Skillbook:
        """Return the Skillbook for *room_id*, loading from disk if needed."""
        with self._lock:
            if room_id not in self._skillbooks:
                path = self._skillbook_path(room_id)
                if path.exists():
                    self._skillbooks[room_id] = Skillbook.load_from_file(
                        str(path),
                    )
                else:
                    self._skillbooks[room_id] = Skillbook()

            return self._skillbooks[room_id]

    def persist(self, room_id: str) -> None:
        """Save the in-memory Skillbook for *room_id* to disk."""
        with self._lock:
            skillbook = self._skillbooks.get(room_id)
            if skillbook is None:
                return

            path = self._skillbook_path(room_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            skillbook.save_to_file(str(path))
