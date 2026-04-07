from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.keywords.dedup import (
    file_hash,
    is_duplicate,
    is_upload_rate_limited,
    mark_uploaded,
    record_upload_attempt,
    upload_rate_limit_status,
)
from apps.keywords.models import Keyword
from apps.keywords.parsers.base import ParseError
from apps.keywords.services import (
    create_keywords_from_list,
    dispatch_scraping,
    parse_keywords_from_file,
)

from .serializers import KeywordListSerializer, KeywordSerializer, UploadFileSerializer


class KeywordUploadAPIView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response(
                {'error': 'No file provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_id = request.user.id

        if is_upload_rate_limited(user_id):
            _, _, reset_in = upload_rate_limit_status(user_id)
            return Response(
                {
                    'error': 'Upload limit reached (10 uploads per hour).',
                    'retry_after_seconds': reset_in,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        hash_value = file_hash(uploaded_file)
        if is_duplicate(user_id, hash_value):
            return Response(
                {'error': f'"{uploaded_file.name}" was already uploaded in the last 5 minutes. Please wait before re-uploading the same file.'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            keyword_texts = parse_keywords_from_file(uploaded_file)
        except ParseError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mark_uploaded(user_id, hash_value)
        record_upload_attempt(user_id)
        upload_file, keywords = create_keywords_from_list(
            request.user, uploaded_file.name, keyword_texts, file_hash=hash_value,
        )
        keyword_ids = [k.id for k in keywords]
        dispatch_scraping(keyword_ids)

        return Response(
            {
                'upload': UploadFileSerializer(upload_file).data,
                'keyword_count': len(keyword_texts),
            },
            status=status.HTTP_201_CREATED,
        )


class KeywordListAPIView(ListAPIView):
    serializer_class = KeywordListSerializer

    def get_queryset(self):
        qs = Keyword.objects.filter(
            upload_file__user=self.request.user,
        ).select_related('upload_file', 'search_result')

        status_filter = self.request.query_params.get('status')
        if status_filter and status_filter in dict(Keyword.Status.choices):
            qs = qs.filter(status=status_filter)

        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(text__icontains=q)

        return qs


class KeywordDetailAPIView(RetrieveAPIView):
    serializer_class = KeywordSerializer

    def get_queryset(self):
        return Keyword.objects.filter(
            upload_file__user=self.request.user,
        ).select_related('upload_file', 'search_result')


class KeywordStatusAPIView(APIView):
    def get(self, request):
        keywords = Keyword.objects.filter(
            upload_file__user=request.user,
        ).values('id', 'text', 'status')
        return Response(list(keywords))
