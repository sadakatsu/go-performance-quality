from dataclasses_json import DataClassJsonMixin, config, Undefined, LetterCase


class SimpleJsonMixin(DataClassJsonMixin):
    # build a marshmallow/dataclasses‑json config dict…
    dataclass_json_config = config(
        undefined=Undefined.EXCLUDE,      # (optional) ignores extra keys on load
        exclude=lambda v: v is None,      # drop any field whose value is None
        letter_case=LetterCase.CAMEL,
    )["dataclasses_json"]
