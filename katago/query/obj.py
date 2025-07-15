from dataclasses import dataclass, field
from typing import List, Optional, Union, Any, Dict

from mashumaro import field_options

from katago.query import Placement, MoveDTO, MoveRestriction
from katago.query.rules import *
from katago.shared import Player
from katago.shared.humanprofile import HumanProfile
from katago.shared.simplejsonmixin import SimpleJsonMixin

HUMAN_PROFILE_SETTING = 'humanSLProfile'
SEARCH_TIME_SETTING = 'maxTime'


@dataclass
class Query(SimpleJsonMixin):
    board_x_size: int
    board_y_size: int
    rules: Union[Ruleset, RulesSpecification]

    moves: List[MoveDTO] = field(default_factory=list)

    allow_moves: Optional[List[MoveRestriction]] = None
    analysis_pv_len: Optional[int] = field(default=None, metadata=field_options(alias="analysisPVLen"))
    analyze_turns: Optional[List[int]] = None
    avoid_moves: Optional[List[MoveRestriction]] = None
    id: Optional[str] = None  # actually required, but this needs to be set by the KataGo publishing code
    include_moves_ownership: Optional[bool] = None
    include_moves_ownership_stdev: Optional[bool] = None
    include_ownership: Optional[bool] = None
    include_ownership_stdev: Optional[bool] = None
    include_policy: Optional[bool] = None
    include_pv_visits: Optional[bool] = field(default=None, metadata=field_options(alias="includePVVisits"))
    initial_player: Optional[Player] = None
    initial_stones: Optional[List[Placement]] = None
    komi: Optional[Union[float, int]] = None
    max_visits: Optional[int] = None
    override_settings: Optional[Dict[str, Any]] = None
    priorities: Optional[List[int]] = None
    priority: Optional[int] = None
    report_during_search_every: Optional[float] = None
    root_fpu_reduction_max: Optional[float] = None
    root_policy_temperature: Optional[float] = None
    white_handicap_bonus: Optional[WhiteHandicapBonus] = None

    def set_human_profile(self, profile: HumanProfile):
        self._update_override_settings(HUMAN_PROFILE_SETTING, profile.value)

    def _update_override_settings(self, key: str, value: Any):
        if self.override_settings is None:
            self.override_settings = {}
        self.override_settings[key] = value

    def remove_human_profile(self):
        if self.override_settings is not None:
            if 'humanSLProfile' in self.override_settings:
                del self.override_settings[HUMAN_PROFILE_SETTING]

    def _remove_override_setting(self, key: str):
        if self.override_settings is not None:
            if key in self.override_settings:
                del self.override_settings[key]

    def set_search_seconds(self, seconds: int):
        self._update_override_settings(SEARCH_TIME_SETTING, seconds)

    def remove_search_seconds(self):
        self._remove_override_setting(SEARCH_TIME_SETTING)
