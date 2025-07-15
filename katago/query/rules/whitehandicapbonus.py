from enum import StrEnum


class WhiteHandicapBonus(StrEnum):
    N = "N"
    N_LESS_1 = "N-1"
    ZERO = "0"

    def __str__(self):
        return self.value
