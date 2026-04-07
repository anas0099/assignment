import os

from .base import BaseKeywordParser, ParseError
from .csv_parser import CSVKeywordParser

_PARSERS: list[type[BaseKeywordParser]] = [
    CSVKeywordParser,
]


def get_parser(filename: str) -> BaseKeywordParser:
    """Return the right parser instance for a given filename.

    Raises ParseError if no registered parser handles the file extension.
    """
    ext = os.path.splitext(filename)[1].lower()
    for parser_cls in _PARSERS:
        if ext in parser_cls.supported_extensions():
            return parser_cls()
    supported = get_supported_extensions()
    raise ParseError(f'Unsupported file type. Allowed: {", ".join(supported)}')


def get_supported_extensions() -> list[str]:
    """Return a flat list of all file extensions supported across all registered parsers."""
    extensions = []
    for parser_cls in _PARSERS:
        extensions.extend(parser_cls.supported_extensions())
    return extensions
