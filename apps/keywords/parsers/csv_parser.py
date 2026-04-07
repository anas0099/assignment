import csv
import io

from .base import BaseKeywordParser, ParseError


class CSVKeywordParser(BaseKeywordParser):
    """Parses CSV files where each cell is treated as a keyword.

    Handles multi-column CSVs - every non-empty cell across all rows is
    collected. Empty cells and whitespace-only values are skipped.
    """

    @classmethod
    def supported_extensions(cls) -> list[str]:
        """Return ['.csv'] as the only supported extension."""
        return ['.csv']

    def parse(self, file_content: bytes) -> list[str]:
        """Decode the CSV bytes and return a validated list of keywords."""
        if len(file_content) > 1 * 1024 * 1024:
            raise ParseError('File is too large. Maximum allowed size is 1 MB.')

        try:
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            raise ParseError('File must be UTF-8 encoded.')

        try:
            reader = csv.reader(io.StringIO(text))
            keywords = []
            for row in reader:
                for cell in row:
                    stripped = cell.strip()
                    if stripped:
                        keywords.append(stripped)
        except csv.Error as e:
            raise ParseError(f'Could not read CSV file: {e}')

        return self.validate(keywords)
