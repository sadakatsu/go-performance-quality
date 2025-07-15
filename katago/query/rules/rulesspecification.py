from dataclasses import dataclass
from typing import Optional

from katago.query.rules import KoRule, ScoringRule, TaxRule, WhiteHandicapBonus
from katago.shared.simplejsonmixin import SimpleJsonMixin


@dataclass
class RulesSpecification(SimpleJsonMixin):
    friendly_pass_ok: bool
    has_button: bool
    ko: KoRule
    score: ScoringRule
    suicide: bool
    tax: TaxRule
    white_handicap_bonus: WhiteHandicapBonus

    # NOTE: While komi can be captured in the RulesSpecification description, but it is better to use the Query's top-
    # level `komi` field.
    komi: Optional[float] = None
