from enum import StrEnum


class Player(StrEnum):
    B = 'B'
    W = 'W'

    def __str__(self):
        return self.value
