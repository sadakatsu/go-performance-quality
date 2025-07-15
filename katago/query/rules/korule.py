from enum import StrEnum


class KoRule(StrEnum):
    POSITIONAL = "positional"
    SIMPLE = "simple"
    SITUATIONAL = "situational"

    def __str__(self):
        return self.value
