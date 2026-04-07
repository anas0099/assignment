"""
CSV upload deduplication and rate limiting.

Deduplication: a SHA256 hash of each uploaded file is stored in Redis for
5 minutes. Uploading the same file twice in that window is blocked.

Rate limiting: a sliding window counter per user tracks how many uploads
they have made in the last RATE_WINDOW_SECONDS. Older timestamps are
trimmed on each check so the window truly slides.
"""
import hashlib
import logging
import time

from decouple import config
from django.core.cache import cache

logger = logging.getLogger(__name__)

DEDUP_TTL = 300
_DEDUP_KEY = 'upload:dedup:{}:{}'

RATE_LIMIT_MAX = config('UPLOAD_RATE_LIMIT_MAX', default=10, cast=int)
RATE_WINDOW_SECONDS = config('UPLOAD_RATE_WINDOW_SECONDS', default=3600, cast=int)
_RATE_KEY = 'upload:rate:{}:window'
_RATE_TS_KEY = 'upload:rate:{}:timestamps'


def file_hash(file_obj):
    """Return the SHA256 hex digest of file_obj's content.

    Seeks to the beginning before reading and resets the position
    afterwards so the caller can still read the file normally.
    """
    file_obj.seek(0)
    digest = hashlib.sha256(file_obj.read()).hexdigest()
    file_obj.seek(0)
    return digest


def is_duplicate(user_id, hash_value):
    """Return True if this file was already uploaded by this user within the last 5 minutes."""
    key = _DEDUP_KEY.format(user_id, hash_value)
    result = cache.get(key)
    logger.debug('dedup check key=%s result=%s', key, result)
    return result is not None


def mark_uploaded(user_id, hash_value):
    """Store the file hash in Redis so subsequent uploads of the same file are blocked."""
    key = _DEDUP_KEY.format(user_id, hash_value)
    cache.set(key, 1, DEDUP_TTL)
    logger.debug('dedup marked key=%s ttl=%d', key, DEDUP_TTL)


def _sliding_window_count(user_id):
    """Return timestamps from within the current window and the current time.

    Fetches the stored list from Redis, drops anything older than the window,
    and returns what is left along with the current unix timestamp.
    """
    key = _RATE_TS_KEY.format(user_id)
    now = time.time()
    cutoff = now - RATE_WINDOW_SECONDS
    timestamps = cache.get(key) or []
    timestamps = [t for t in timestamps if t > cutoff]
    return timestamps, now


def is_upload_rate_limited(user_id):
    """Return True if the user has hit the upload limit for the current window."""
    timestamps, _ = _sliding_window_count(user_id)
    return len(timestamps) >= RATE_LIMIT_MAX


def record_upload_attempt(user_id):
    """Record a successful upload timestamp for this user in Redis."""
    key = _RATE_TS_KEY.format(user_id)
    timestamps, now = _sliding_window_count(user_id)
    timestamps.append(now)
    cache.set(key, timestamps, RATE_WINDOW_SECONDS)


def upload_rate_limit_status(user_id):
    """Return a tuple of (uploads_used, uploads_remaining, seconds_until_reset).

    seconds_until_reset is calculated from the oldest timestamp in the window.
    Returns 0 for reset_in if no uploads have been recorded yet.
    """
    timestamps, now = _sliding_window_count(user_id)
    used = len(timestamps)
    remaining = max(0, RATE_LIMIT_MAX - used)
    reset_in = 0
    if timestamps:
        oldest = min(timestamps)
        reset_in = max(0, int(RATE_WINDOW_SECONDS - (now - oldest)))
    return used, remaining, reset_in
