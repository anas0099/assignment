from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, SignUpSerializer


class SignUpAPIView(APIView):
    """REST endpoint for creating a new user account.

    Returns a DRF token on success so the client can immediately start
    making authenticated requests without a separate login call.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """Create the user and return a token, user_id, and username."""
        serializer = SignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {'token': token.key, 'user_id': user.pk, 'username': user.username},
            status=status.HTTP_201_CREATED,
        )


class LoginAPIView(APIView):
    """REST endpoint for authenticating an existing user.

    Returns the same token format as SignUpAPIView so clients can handle
    both responses the same way.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """Validate credentials and return a token, or 401 if they are wrong."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )
        if user is None:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user_id': user.pk, 'username': user.username})
