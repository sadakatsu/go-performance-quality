from dataclasses import dataclass

from katago.shared.simplejsonmixin import SimpleJsonMixin


@dataclass
class WarningResponse(SimpleJsonMixin):
    field: str
    id: str
    warning: str
