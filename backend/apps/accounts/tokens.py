"""JWT tokens with a version claim so passwords can invalidate old tokens."""
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class VersionedTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["ver"] = user.token_version
        return token


class VersionedJWTAuthentication(JWTAuthentication):
    """Rejects access tokens whose ``ver`` claim no longer matches the user."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        token_ver = validated_token.get("ver", 0)
        if user.token_version != token_ver:
            raise InvalidToken("Token is no longer valid.")
        return user
