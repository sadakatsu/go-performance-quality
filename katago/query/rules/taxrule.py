from enum import StrEnum


class TaxRule(StrEnum):
    ALL = 'all'
    NONE = 'none'
    SEKI = 'seki'

    def __str__(self):
        return self.value
