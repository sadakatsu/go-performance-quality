from dataclasses import dataclass, field
from typing import Union, Dict

from mashumaro import field_options
from mashumaro.mixins.yaml import DataClassYAMLMixin

from katago.shared.humanprofile import HumanProfile


@dataclass
class LaunchConfiguration(DataClassYAMLMixin):
    config: str
    executable: str
    profile: HumanProfile

    analysis_threads: int = field(metadata=field_options(alias="analysisThreads"))
    human_model: str = field(metadata=field_options(alias="humanModel"))
    search_model: str = field(metadata=field_options(alias="searchModel"))
    search_threads: int = field(metadata=field_options(alias="searchThreads"))

    override_config: Dict[str, Union[float, int, str]] | None = field(
        default=None,
        metadata=field_options(alias="overrideConfig")
    )
    playouts: int = field(default=16384)
    visits: int = field(default=1048576)
    fastQuit: bool = field(default=True, metadata=field_options(alias="fastQuit"))

    @property
    def launch_script(self) -> str:
        representation = (
            f'{self.executable} analysis '
            f'-config {self.config} '
            f'-model {self.search_model} '
            f'-human-model {self.human_model} '
            f'-override-config humanSLProfile={self.profile},'
            f'numAnalysisThreads={self.analysis_threads},'
            f'numSearchThreads={self.search_threads},'
            f'maxPlayouts={self.playouts},'
            f'maxVisits={self.visits},'
            f'reportAnalysisWinrateAs=SIDETOMOVE' # hardcoded because this application cannot work well otherwise!
        )
        if self.fastQuit:
            representation += ' -quit-without-waiting'
        if self.override_config is not None:
            for key, value in self.override_config.items():
                representation += f' -override-config {key}={value}'
        return representation
