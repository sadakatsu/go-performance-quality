from enum import StrEnum

from katago.query.rules import KoRule, ScoringRule, TaxRule, WhiteHandicapBonus
from katago.query.rules import RulesSpecification


class Ruleset(StrEnum):
    # These are grouped with their synonyms according to
    # https://github.com/lightvector/KataGo/blob/f5756b1b6224500c1dd9ced62408a85766b5f45c/cpp/game/rules.cpp#L332
    AGA = "aga"
    BGA = "bga"
    FRENCH = "french"

    AGA_BUTTON = "aga-button"

    ANCIENT_AREA = "ancient-area"
    STONE_SCORING = "stone-scoring"

    ANCIENT_TERRITORY = "ancient-territory"

    CHINESE = "chinese"

    CHINESE_KGS = "chinese-kgs"
    CHINESE_OGS = "chinese-ogs"

    GOE = "goe"
    ING = "ing"

    JAPANESE = "japanese"
    KOREAN = "korean"

    NEW_ZEALAND = "new-zealand"

    TROMP_TAYLOR = "tromp-taylor"

    def __str__(self):
        return self.value

    @property
    def specification(self) -> RulesSpecification:
        if self in (Ruleset.JAPANESE, Ruleset.KOREAN):
            specification = RulesSpecification(
                has_button=False,
                friendly_pass_ok=False,  # bizarre but, yes, KataGo treats Japanese rules as forcing all captures!
                ko=KoRule.SIMPLE,
                komi=6.5,
                score=ScoringRule.TERRITORY,
                suicide=False,
                white_handicap_bonus=WhiteHandicapBonus.ZERO,
                tax=TaxRule.SEKI,
            )
        elif self == Ruleset.CHINESE:
            specification = RulesSpecification(
                has_button=False,
                friendly_pass_ok=True,
                ko=KoRule.SIMPLE,
                komi=7.5,
                score=ScoringRule.AREA,
                suicide=False,
                white_handicap_bonus=WhiteHandicapBonus.N,
                tax=TaxRule.NONE,
            )
        elif self in (Ruleset.CHINESE_KGS, Ruleset.CHINESE_OGS):
            specification = RulesSpecification(
                has_button=False,
                friendly_pass_ok=True,
                ko=KoRule.POSITIONAL,
                komi=7.5,
                score=ScoringRule.AREA,
                suicide=False,
                white_handicap_bonus=WhiteHandicapBonus.N,
                tax=TaxRule.NONE,
            )
        elif self in (Ruleset.ANCIENT_AREA, Ruleset.STONE_SCORING):
            specification = RulesSpecification(
                has_button=False,
                friendly_pass_ok=True,
                ko=KoRule.SIMPLE,
                komi=7.5,  # ... really?  okay then
                score=ScoringRule.AREA,
                suicide=False,
                white_handicap_bonus=WhiteHandicapBonus.ZERO,
                tax=TaxRule.ALL,
            )
        elif self == Ruleset.ANCIENT_TERRITORY:
            specification = RulesSpecification(
                has_button=False,
                friendly_pass_ok=False,
                ko=KoRule.SIMPLE,
                komi=6.5,
                score=ScoringRule.TERRITORY,
                suicide=False,
                white_handicap_bonus=WhiteHandicapBonus.ZERO,
                tax=TaxRule.ALL,
            )
        elif self == Ruleset.AGA_BUTTON:
            specification = RulesSpecification(
                has_button=True,
                friendly_pass_ok=True,
                ko=KoRule.SITUATIONAL,
                komi=7.0,
                score=ScoringRule.AREA,
                suicide=False,
                white_handicap_bonus=WhiteHandicapBonus.N_LESS_1,
                tax=TaxRule.NONE,
            )
        elif self in (Ruleset.AGA, Ruleset.BGA, Ruleset.FRENCH):
            specification = RulesSpecification(
                has_button=False,
                friendly_pass_ok=True,
                ko=KoRule.SITUATIONAL,
                komi=7.5,
                score=ScoringRule.AREA,
                suicide=False,
                white_handicap_bonus=WhiteHandicapBonus.N_LESS_1,
                tax=TaxRule.NONE,
            )
        elif self == Ruleset.NEW_ZEALAND:
            specification = RulesSpecification(
                has_button=False,
                friendly_pass_ok=True,
                ko=KoRule.SITUATIONAL,
                komi=7.5,
                score=ScoringRule.AREA,
                suicide=True,
                white_handicap_bonus=WhiteHandicapBonus.ZERO,
                tax=TaxRule.NONE,
            )
        elif self == Ruleset.TROMP_TAYLOR:
            specification = RulesSpecification(
                has_button=False,
                friendly_pass_ok=False,
                ko=KoRule.POSITIONAL,
                komi=7.5,
                score=ScoringRule.AREA,
                suicide=True,
                white_handicap_bonus=WhiteHandicapBonus.ZERO,
                tax=TaxRule.NONE,
            )
        elif self in (Ruleset.GOE, Ruleset.ING):
            specification = RulesSpecification(
                has_button=False,
                friendly_pass_ok=True,
                ko=KoRule.POSITIONAL,
                komi=7.5,
                score=ScoringRule.AREA,
                suicide=True,
                white_handicap_bonus=WhiteHandicapBonus.ZERO,
                tax=TaxRule.NONE,
            )


        return specification