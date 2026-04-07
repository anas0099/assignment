from django.contrib import admin

from .models import Keyword, SearchResult, UploadFile


@admin.register(UploadFile)
class UploadFileAdmin(admin.ModelAdmin):
    """Admin view for CSV upload records. Useful for auditing what files each user has submitted."""

    list_display = ('file_name', 'user', 'total_keywords', 'created_at')
    list_filter = ('created_at',)


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    """Admin view for individual keywords. Filterable by status so stuck or failed keywords are easy to spot."""

    list_display = ('text', 'status', 'retry_count', 'created_at')
    list_filter = ('status',)
    search_fields = ('text',)


@admin.register(SearchResult)
class SearchResultAdmin(admin.ModelAdmin):
    """Admin view for scraped results. Shows ad count and link count at a glance."""

    list_display = ('keyword', 'total_ads', 'total_links', 'scraped_at')
