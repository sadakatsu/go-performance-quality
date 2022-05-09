from __future__ import annotations
from domain.coordinate import Coordinate
from enum import Enum
from typing import Callable

from domain.pass_enum import Pass


def get_column(coordinate: Coordinate) -> int:
    return coordinate.column


def get_column_opposite(coordinate: Coordinate) -> int:
    return 18 - coordinate.column


def get_row(coordinate: Coordinate) -> int:
    return coordinate.row


def get_row_opposite(coordinate: Coordinate) -> int:
    return 18 - coordinate.row


class Orientation(Enum):
    UNCHANGED = (0, get_column, get_row)
    MIRROR_HORIZONTAL = (1, get_column_opposite, get_row)
    MIRROR_VERTICAL = (2, get_column, get_row_opposite)
    ROTATE_TWICE = (3, get_column_opposite, get_row_opposite)
    MIRROR_LEFT_DIAGONAL = (4, get_row, get_column)
    ROTATE_LEFT = (5, get_row_opposite, get_column)
    ROTATE_RIGHT = (6, get_row, get_column_opposite)
    MIRROR_RIGHT_DIAGONAL = (7, get_row_opposite, get_column_opposite)

    def __init__(self, ordinal, next_column: Callable[[Coordinate], int], next_row: Callable[[Coordinate], int]):
        self._next_column = next_column
        self._next_row = next_row
        self._ordinal = ordinal
        self._undo = None

    @property
    def ordinal(self) -> int:
        return self._ordinal

    @classmethod
    def by_ordinal(cls, ordinal: int) -> Orientation:
        if not hasattr(cls, '_values'):
            cls._values = [x for x in cls]
        if not (0 <= ordinal < 8):
            raise Exception(f'Received an invalid Orientation ordinal {ordinal}.')
        return cls._values[ordinal]

    def transform(self, move: Coordinate | Pass) -> Coordinate | Pass:
        if type(move) == Pass:
            result = move
        else:
            c = self._next_column(move)
            r = self._next_row(move)
            result = Coordinate.get(c, r)
        return result

    def undo(self, move: Coordinate | Pass) -> Coordinate | Pass:
        if not self._undo:
            if self == Orientation.ROTATE_LEFT:
                self._undo = Orientation.ROTATE_RIGHT
            elif self == Orientation.ROTATE_RIGHT:
                self._undo = Orientation.ROTATE_LEFT
            else:
                self._undo = self

        return self._undo.transform(move)
