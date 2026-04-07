from abc import ABC, abstractmethod


class ParseError(Exception):
    """Raised when a file cannot be parsed into a valid keyword list."""


class BaseKeywordParser(ABC):
    """Abstract base for all keyword file parsers.

    Subclasses implement parse() and supported_extensions(). The validate()
    method is shared and enforces the keyword count limits.
    """

    @abstractmethod
    def parse(self, file_content: bytes) -> list[str]:
        """Parse raw file bytes and return a clean list of keyword strings."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def supported_extensions(cls) -> list[str]:
        """Return the list of file extensions this parser handles, e.g. ['.csv']."""
        raise NotImplementedError

    def validate(self, keywords: list[str], max_keywords: int = 100, max_keyword_length: int = 500) -> list[str]:
        """Check that the keyword list is non-empty, within the allowed limit, and each keyword is not too long."""
        if not keywords:
            raise ParseError('File contains no keywords.')
        if len(keywords) > max_keywords:
            raise ParseError(f'Maximum {max_keywords} keywords allowed per file. Found {len(keywords)}.')
        too_long = [kw[:40] + '...' for kw in keywords if len(kw) > max_keyword_length]
        if too_long:
            raise ParseError(
                f'{len(too_long)} keyword(s) exceed the {max_keyword_length} character limit: '
                + ', '.join(f'"{kw}"' for kw in too_long[:3])
                + (f' and {len(too_long) - 3} more' if len(too_long) > 3 else '')
            )
        return keywords
