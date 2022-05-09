from enum import Enum


class Color(Enum):
    EMPTY = (0, True, True)
    BLACK = (1, False, False)
    WHITE = (2, False, False)
    TEMPORARILY_UNPLAYABLE = (3, True, False)

    def __init__(self, code, counts_as_liberty, playable):
        self._code = code
        self._counts_as_liberty = counts_as_liberty
        self._playable = playable
        self._opposite = None

    @property
    def code(self):
        return self._code

    @property
    def opposite(self):
        if not self._opposite:
            if self == Color.BLACK:
                self._opposite = Color.WHITE
            elif self == Color.WHITE:
                self._opposite = Color.BLACK
            else:
                self._opposite = self
        return self._opposite

    @property
    def counts_as_liberty(self):
        return self._counts_as_liberty

    @property
    def playable(self):
        return self._playable
