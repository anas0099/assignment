from abc import ABC, abstractmethod


class ParseError(Exception):
    pass


class BaseKeywordParser(ABC):
    @abstractmethod
    def parse(self, file_content: bytes) -> list[str]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def supported_extensions(cls) -> list[str]:
        raise NotImplementedError

    def validate(self, keywords: list[str], max_keywords: int = 100) -> list[str]:
        if not keywords:
            raise ParseError('File contains no keywords.')
        if len(keywords) > max_keywords:
            raise ParseError(f'Maximum {max_keywords} keywords allowed per file.')
        return keywords
