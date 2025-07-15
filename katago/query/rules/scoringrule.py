from enum import StrEnum


class ScoringRule(StrEnum):
    AREA = "area"
    TERRITORY = "territory"

    def __str__(self):
        return self.value
