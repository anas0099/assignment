from .models import Keyword, UploadFile
from .parsers import get_parser


def parse_keywords_from_file(uploaded_file) -> list[str]:
    parser = get_parser(uploaded_file.name)
    content = uploaded_file.read()
    uploaded_file.seek(0)
    return parser.parse(content)


def create_keywords_from_list(user, file_name, keyword_texts):
    upload_file = UploadFile.objects.create(
        user=user,
        file_name=file_name,
        total_keywords=len(keyword_texts),
    )
    keywords = Keyword.objects.bulk_create([
        Keyword(upload_file=upload_file, text=text)
        for text in keyword_texts
    ])
    return upload_file, keywords


def dispatch_scraping(keyword_ids):
    from django.conf import settings

    if settings.SCRAPING_MODE == 'async':
        pass
    else:
        from apps.scraper.engine import scrape_keyword_sync
        for keyword_id in keyword_ids:
            try:
                scrape_keyword_sync(keyword_id)
            except Exception:
                pass
