from enum import Enum

from domain.korule import KoRule
from domain.scoring import Scoring


class Ruleset(Enum):
    AGA = (KoRule.SITUATIONAL, Scoring.AREA)
    AGA_BUTTON = (KoRule.SITUATIONAL, Scoring.AREA)
    BGA = (KoRule.SITUATIONAL, Scoring.AREA)
    CHINESE = (KoRule.SIMPLE, Scoring.AREA)
    CHINESE_KGS = (KoRule.POSITIONAL, Scoring.AREA)
    CHINESE_OGS = (KoRule.POSITIONAL, Scoring.AREA)
    JAPANESE = (KoRule.SIMPLE, Scoring.TERRITORY)
    KOREAN = (KoRule.SIMPLE, Scoring.TERRITORY)
    NEW_ZEALAND = (KoRule.SITUATIONAL, Scoring.AREA)
    STONE_SCORING = (KoRule.SIMPLE, Scoring.AREA)
    TROMP_TAYLOR = (KoRule.POSITIONAL, Scoring.AREA)

    def __init__(self, ko_rule, scoring):
        self._ko_rule = ko_rule
        self._scoring = scoring

        self._command = self.name.lower() \
            .replace('_', '-')

    @property
    def command(self):
        return self._command

    @property
    def ko_rule(self):
        return self._ko_rule

    @property
    def scoring(self):
        return self._scoring
