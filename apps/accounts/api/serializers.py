from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class SignUpSerializer(serializers.Serializer):
    """Validates and creates a new user via the REST API.

    Password is write-only so it never appears in response payloads.
    Uniqueness checks on username and email are done here rather than in the
    view to keep validation logic in one place.
    """

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        """Reject the request if the username is already taken."""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already taken.')
        return value

    def validate_email(self, value):
        """Reject the request if the email address is already registered."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value

    def create(self, validated_data):
        """Create the user with a properly hashed password."""
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
        )


class LoginSerializer(serializers.Serializer):
    """Validates login credentials passed to the REST API."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
