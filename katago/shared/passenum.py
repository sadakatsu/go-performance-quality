from enum import StrEnum


class Pass(StrEnum):
    PASS = "pass"

    def __str__(self):
        return self.value
