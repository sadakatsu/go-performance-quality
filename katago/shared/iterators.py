from typing import Iterator, Tuple, Union

from katago.shared import Coordinate, Pass


def coordinate_iterator(size: int) -> Iterator[Tuple[int, Coordinate]]:
    if size > 19:
        raise ValueError('size must be <= 19')

    nested_generator = (
        Coordinate(f'{column}{row}')
        for row in range(size, 0, -1)
        for column in 'ABCDEFGHJKLMNOPQRST'[:size]
    )
    for index, coordinate in enumerate(nested_generator):
        yield index, coordinate


def move_iterator(size: int) -> Iterator[Tuple[int, Union[Coordinate, Pass]]]:
    for index, coordinate in coordinate_iterator(size):
        yield index, coordinate

    yield size * size, Pass.PASS
