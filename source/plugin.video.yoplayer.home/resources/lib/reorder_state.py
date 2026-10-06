"""Private reorder drafts, independent of Kodi controls and persistence."""
import copy


class ReorderState:
    visible_count = 8

    def __init__(self, rows):
        self.original = copy.deepcopy(rows)
        self.rows = copy.deepcopy(rows)
        self.focus = 0
        self.start = 0
        self.lifted = None

    @property
    def dirty(self):
        return self.rows != self.original

    def ensure_visible(self):
        self.start = min(self.start, self.focus)
        self.start = max(self.start, self.focus - self.visible_count + 1)
        self.start = max(0, min(self.start, len(self.rows) - self.visible_count))

    def select(self, index):
        if self.lifted is None and 0 <= index < len(self.rows):
            self.focus = index
            self.ensure_visible()

    def toggle(self):
        if not self.rows:
            return
        if self.lifted is None:
            self.lifted = (copy.deepcopy(self.rows), self.focus)
        else:
            self.lifted = None

    def step(self, delta):
        target = self.focus + delta
        if not 0 <= target < len(self.rows):
            return False
        if self.lifted is not None:
            row = self.rows.pop(self.focus)
            self.rows.insert(target, row)
        self.focus = target
        self.ensure_visible()
        return True

    def undo_lift(self):
        if self.lifted is None:
            return False
        self.rows, self.focus = self.lifted
        self.lifted = None
        self.ensure_visible()
        return True

    def finish(self):
        if self.lifted is not None:
            return None
        return copy.deepcopy(self.rows)
