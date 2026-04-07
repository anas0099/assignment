import hashlib
import time

from decouple import config
from django.core.cache import cache

DEDUP_TTL = 300
_DEDUP_KEY = 'upload:dedup:{}:{}'

RATE_LIMIT_MAX = config('UPLOAD_RATE_LIMIT_MAX', default=10, cast=int)
RATE_WINDOW_SECONDS = config('UPLOAD_RATE_WINDOW_SECONDS', default=3600, cast=int)
_RATE_KEY = 'upload:rate:{}:window'
_RATE_TS_KEY = 'upload:rate:{}:timestamps'


def file_hash(file_obj):
    file_obj.seek(0)
    digest = hashlib.sha256(file_obj.read()).hexdigest()
    file_obj.seek(0)
    return digest


def is_duplicate(user_id, hash_value):
    return cache.get(_DEDUP_KEY.format(user_id, hash_value)) is not None


def mark_uploaded(user_id, hash_value):
    cache.set(_DEDUP_KEY.format(user_id, hash_value), 1, DEDUP_TTL)


def _sliding_window_count(user_id):
    key = _RATE_TS_KEY.format(user_id)
    now = time.time()
    cutoff = now - RATE_WINDOW_SECONDS
    timestamps = cache.get(key) or []
    timestamps = [t for t in timestamps if t > cutoff]
    return timestamps, now


def is_upload_rate_limited(user_id):
    timestamps, _ = _sliding_window_count(user_id)
    return len(timestamps) >= RATE_LIMIT_MAX


def record_upload_attempt(user_id):
    key = _RATE_TS_KEY.format(user_id)
    timestamps, now = _sliding_window_count(user_id)
    timestamps.append(now)
    cache.set(key, timestamps, RATE_WINDOW_SECONDS)


def upload_rate_limit_status(user_id):
    timestamps, now = _sliding_window_count(user_id)
    used = len(timestamps)
    remaining = max(0, RATE_LIMIT_MAX - used)
    reset_in = 0
    if timestamps:
        oldest = min(timestamps)
        reset_in = max(0, int(RATE_WINDOW_SECONDS - (now - oldest)))
    return used, remaining, reset_in
