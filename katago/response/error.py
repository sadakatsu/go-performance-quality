from dataclasses import dataclass
from typing import Optional

from katago.shared.simplejsonmixin import SimpleJsonMixin


@dataclass
class ErrorResponse(SimpleJsonMixin):
    error: str

    field: Optional[str] = None
    id: Optional[str] = None
