from django.conf import settings
from django.db import models


class UploadFile(models.Model):
    """Tracks each CSV file a user has uploaded.

    Stores the original filename, a SHA256 hash of the file content for
    deduplication, and how many keywords were parsed from it.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='upload_files',
    )
    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, blank=True, default='')
    total_keywords = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        """Human-readable label shown in the admin and debug output."""
        return f'{self.file_name} ({self.total_keywords} keywords)'


class Keyword(models.Model):
    """A single search term queued for scraping.

    Moves through pending -> processing -> completed / failed.
    retry_count tracks how many times scraping has been attempted.
    error_message stores the last failure reason for debugging.
    """

    class Status(models.TextChoices):
        """The processing states a keyword moves through during its lifecycle."""

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
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        """Return the keyword text as its string representation."""
        return self.text

    @property
    def user(self):
        """Shortcut to get the user who owns this keyword via the upload file."""
        return self.upload_file.user


class SearchResult(models.Model):
    """Stores the scraped data for a completed keyword.

    db_constraint=False on the keyword FK is required because the keywords
    table uses PostgreSQL range partitioning with a composite primary key,
    which prevents standard FK constraints from working across partitions.
    """

    keyword = models.OneToOneField(
        Keyword,
        on_delete=models.CASCADE,
        related_name='search_result',
        db_constraint=False,
    )
    total_ads = models.PositiveIntegerField(default=0)
    total_links = models.PositiveIntegerField(default=0)
    raw_html = models.TextField(blank=True, default='')
    scraped_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Return a readable label identifying which keyword this result belongs to."""
        return f'Result for: {self.keyword.text}'
