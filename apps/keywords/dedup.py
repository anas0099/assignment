import hashlib

from django.core.cache import cache

DEDUP_TTL = 300
_KEY = 'upload:dedup:{}:{}'


def file_hash(file_obj):
    file_obj.seek(0)
    digest = hashlib.sha256(file_obj.read()).hexdigest()
    file_obj.seek(0)
    return digest


def is_duplicate(user_id, hash_value):
    return cache.get(_KEY.format(user_id, hash_value)) is not None


def mark_uploaded(user_id, hash_value):
    cache.set(_KEY.format(user_id, hash_value), 1, DEDUP_TTL)
