import csv
import io

from .base import BaseKeywordParser, ParseError


class CSVKeywordParser(BaseKeywordParser):
    @classmethod
    def supported_extensions(cls) -> list[str]:
        return ['.csv']

    def parse(self, file_content: bytes) -> list[str]:
        try:
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            raise ParseError('File must be UTF-8 encoded.')

        reader = csv.reader(io.StringIO(text))
        keywords = []
        for row in reader:
            for cell in row:
                stripped = cell.strip()
                if stripped:
                    keywords.append(stripped)

        return self.validate(keywords)
