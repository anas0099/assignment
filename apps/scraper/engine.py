from apps.keywords.models import Keyword, SearchResult


def scrape_keyword_sync(keyword_id):
    keyword = Keyword.objects.get(id=keyword_id)
    keyword.status = Keyword.Status.PROCESSING
    keyword.save(update_fields=['status', 'updated_at'])

    keyword.status = Keyword.Status.COMPLETED
    keyword.save(update_fields=['status', 'updated_at'])

    SearchResult.objects.update_or_create(
        keyword=keyword,
        defaults={
            'total_ads': 0,
            'total_links': 0,
            'raw_html': '<p>Placeholder - scraper not yet implemented</p>',
        },
    )
