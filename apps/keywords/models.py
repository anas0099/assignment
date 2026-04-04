from django.conf import settings
from django.db import models


class UploadFile(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='upload_files',
    )
    file_name = models.CharField(max_length=255)
    total_keywords = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.file_name} ({self.total_keywords} keywords)'


class Keyword(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    upload_file = models.ForeignKey(
        UploadFile,
        on_delete=models.CASCADE,
        related_name='keywords',
    )
    text = models.CharField(max_length=500)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    retry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.text

    @property
    def user(self):
        return self.upload_file.user


class SearchResult(models.Model):
    keyword = models.OneToOneField(
        Keyword,
        on_delete=models.CASCADE,
        related_name='search_result',
    )
    total_ads = models.PositiveIntegerField(default=0)
    total_links = models.PositiveIntegerField(default=0)
    raw_html = models.TextField(blank=True, default='')
    scraped_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Result for: {self.keyword.text}'
