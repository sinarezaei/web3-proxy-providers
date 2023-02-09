import json
from typing import (
    Any,
    Dict,
    Iterable,
    Optional,
    Type,
)
from eth_utils import (
    is_list_like,
)


class FriendlyJsonSerde:
    """
    Friendly JSON serializer & deserializer

    When encoding or decoding fails, this class collects
    information on which fields failed, to show more
    helpful information in the raised error messages.
    """
    def _json_mapping_errors(self, mapping: Dict[Any, Any]) -> Iterable[str]:
        for key, val in mapping.items():
            try:
                self._friendly_json_encode(val)
            except TypeError as exc:
                yield "%r: because (%s)" % (key, exc)

    def _json_list_errors(self, iterable: Iterable[Any]) -> Iterable[str]:
        for index, element in enumerate(iterable):
            try:
                self._friendly_json_encode(element)
            except TypeError as exc:
                yield "%d: because (%s)" % (index, exc)

    def _friendly_json_encode(self, obj: Dict[Any, Any],
                              cls: Optional[Type[json.JSONEncoder]] = None) -> str:
        try:
            encoded = json.dumps(obj, cls=cls)
            return encoded
        except TypeError as full_exception:
            if hasattr(obj, 'items'):
                item_errors = '; '.join(self._json_mapping_errors(obj))
                raise TypeError("dict had unencodable value at keys: {{{}}}".format(item_errors))
            elif is_list_like(obj):
                element_errors = '; '.join(self._json_list_errors(obj))
                raise TypeError("list had unencodable value at index: [{}]".format(element_errors))
            else:
                raise full_exception

    def json_decode(self, json_str: str) -> Dict[Any, Any]:
        try:
            decoded = json.loads(json_str)
            return decoded
        except json.decoder.JSONDecodeError as exc:
            err_msg = 'Could not decode {} because of {}.'.format(repr(json_str), exc)
            # Calling code may rely on catching JSONDecodeError to recognize bad json
            # so we have to re-raise the same type.
            raise json.decoder.JSONDecodeError(err_msg, exc.doc, exc.pos)

    def json_encode(self, obj: Dict[Any, Any],
                    cls: Optional[Type[json.JSONEncoder]] = None) -> str:
        try:
            return self._friendly_json_encode(obj, cls=cls)
        except TypeError as exc:
            raise TypeError("Could not encode to JSON: {}".format(exc))