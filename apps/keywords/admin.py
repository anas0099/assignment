from django.contrib import admin

from .models import Keyword, SearchResult, UploadFile


@admin.register(UploadFile)
class UploadFileAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'user', 'total_keywords', 'created_at')
    list_filter = ('created_at',)


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ('text', 'status', 'retry_count', 'created_at')
    list_filter = ('status',)
    search_fields = ('text',)


@admin.register(SearchResult)
class SearchResultAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'total_ads', 'total_links', 'scraped_at')
