from typing import List, Optional, Set

from domain.board import Board
from domain.color import Color
from domain.coordinate import Coordinate


class Group:
    def __init__(self, board: Board, start: Coordinate):
        borders_black = False
        borders_white = False
        liberties = 0
        color = board.get(start)
        members = set()

        queue: List[Optional[Coordinate]] = [None for _ in range(361)]
        queue[0] = start
        seen: List[Optional[Color]] = [None for _ in range(361)]
        seen[start.index] = color

        i = 0
        end = 1
        while i < end:
            current: Coordinate = queue[i]
            current_index = current.index
            current_color = seen[current_index]

            if color == current_color or color.counts_as_liberty and current_color.counts_as_liberty:
                members.add(current)
                current_column = current.column
                current_row = current.row
                if current_row - 1 >= 0:
                    end = Group._update_search(current_column, current_row - 1, seen, queue, end, board)
                if current_row + 1 <= 18:
                    end = Group._update_search(current_column, current_row + 1, seen, queue, end, board)
                if current_column - 1 >= 0:
                    end = Group._update_search(current_column - 1, current_row, seen, queue, end, board)
                if current_column + 1 <= 18:
                    end = Group._update_search(current_column + 1, current_row, seen, queue, end, board)
            elif current_color.counts_as_liberty:
                liberties += 1
            elif current_color == Color.BLACK:
                borders_black = True
            elif current_color == Color.WHITE:
                borders_white = True

            i += 1

        self._color = Color.EMPTY if color == Color.TEMPORARILY_UNPLAYABLE else color
        self._borders_black = borders_black
        self._borders_white = borders_white
        self._liberties = liberties
        self._members = members

    @staticmethod
    def _update_search(
        column: int,
        row: int,
        seen: List[Optional[Color]],
        queue: List[Optional[Coordinate]],
        end: int,
        board: Board
    ) -> int:
        result = end

        neighbor = Coordinate.get(column, row)
        index = neighbor.index
        if not seen[index]:
            queue[end] = neighbor
            color = board.get(neighbor)
            seen[index] = color
            result += 1

        return result

    @property
    def color(self) -> Color:
        return self._color

    @property
    def borders_black(self) -> bool:
        return self._borders_black

    @property
    def borders_white(self) -> bool:
        return self._borders_white

    @property
    def liberties(self) -> int:
        return self._liberties

    @property
    def members(self) -> Set[Coordinate]:
        return {*self._members}

    def __len__(self) -> int:
        return len(self._members)

    def __eq__(self, rhs) -> bool:
        return (
            super().__eq__(rhs) or
            type(rhs) == Group and
            self._borders_black == (Group(rhs))._borders_black and
            self._borders_white == (Group(rhs))._borders_white and
            self._liberties == (Group(rhs))._liberties and
            self._color == (Group(rhs))._color and
            self._members == (Group(rhs))._members
        )

    def __hash__(self) -> int:
        return (self._borders_black, self._borders_white, self._liberties, self._color, self._members).__hash__()
