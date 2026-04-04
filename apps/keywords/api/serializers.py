from rest_framework import serializers

from apps.keywords.models import Keyword, SearchResult, UploadFile


class SearchResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchResult
        fields = ('total_ads', 'total_links', 'raw_html', 'scraped_at')


class KeywordSerializer(serializers.ModelSerializer):
    search_result = SearchResultSerializer(read_only=True)
    file_name = serializers.CharField(source='upload_file.file_name', read_only=True)

    class Meta:
        model = Keyword
        fields = ('id', 'text', 'status', 'retry_count', 'file_name', 'search_result', 'created_at', 'updated_at')


class KeywordListSerializer(serializers.ModelSerializer):
    file_name = serializers.CharField(source='upload_file.file_name', read_only=True)
    has_result = serializers.SerializerMethodField()

    class Meta:
        model = Keyword
        fields = ('id', 'text', 'status', 'file_name', 'has_result', 'created_at')

    def get_has_result(self, obj):
        return hasattr(obj, 'search_result')


class UploadFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadFile
        fields = ('id', 'file_name', 'total_keywords', 'created_at')
