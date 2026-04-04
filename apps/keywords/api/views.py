import csv
import io

from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.keywords.models import Keyword
from apps.keywords.services import create_keywords_from_list, dispatch_scraping

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
        if not uploaded_file.name.endswith('.csv'):
            return Response(
                {'error': 'Only CSV files are allowed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            content = uploaded_file.read().decode('utf-8')
            reader = csv.reader(io.StringIO(content))
            keyword_texts = []
            for row in reader:
                for cell in row:
                    stripped = cell.strip()
                    if stripped:
                        keyword_texts.append(stripped)
        except UnicodeDecodeError:
            return Response(
                {'error': 'File must be UTF-8 encoded.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not keyword_texts:
            return Response(
                {'error': 'CSV file is empty.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(keyword_texts) > 100:
            return Response(
                {'error': 'Maximum 100 keywords allowed per file.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        upload_file, keywords = create_keywords_from_list(
            request.user, uploaded_file.name, keyword_texts,
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
