from django.conf import settings
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response


def oauth_metadata(request):
    """Provide OAuth2 provider metadata."""
    return {
        "issuer": settings.SITE_URL,
        "authorization_endpoint": request.build_absolute_uri(reverse("authorize")),
        "token_endpoint": request.build_absolute_uri(reverse("token")),
        "registration_endpoint": request.build_absolute_uri(reverse("oauth2_dcr")),
        "userinfo_endpoint": request.build_absolute_uri(reverse("user-info")),
        "introspection_endpoint": request.build_absolute_uri(reverse("introspect")),
        "jwks_uri": request.build_absolute_uri(reverse("jwks-info")),
        "revocation_endpoint": request.build_absolute_uri(reverse("revoke-token")),
        "scopes_supported": ["read", "write", "users", "groups"],
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
        "code_challenge_methods_supported": ["plain", "S256"],
    }


# Enhanced serializers with comprehensive field coverage
class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with core fields."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "full_name", "date_joined", "is_active")
        read_only_fields = ("id", "date_joined", "full_name")

    def get_full_name(self, obj) -> str:
        """Return user's full name."""
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


class UserDetailSerializer(UserSerializer):
    """Detailed serializer for User with additional information."""

    group_count = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ("group_count", "last_login", "is_staff", "is_superuser")

    def get_group_count(self, obj) -> int:
        """Return number of groups user belongs to."""
        return obj.groups.count()


class GroupSerializer(serializers.ModelSerializer):
    """Serializer for Group model."""

    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ("id", "name", "user_count")
        read_only_fields = ("id", "user_count")

    def get_user_count(self, obj) -> int:
        """Return number of users in this group."""
        return obj.user_set.count()


# Enhanced ViewSets with comprehensive filtering and search
@extend_schema_view(
    list=extend_schema(
        operation_id="users_list",
        summary="List all users",
        description="List all users with filtering and search capabilities",
        tags=["users"],
        responses={
            200: OpenApiResponse(description="Paginated list of system users"),
        },
    ),
    create=extend_schema(
        operation_id="users_create",
        summary="Create user",
        description="Create a new user account",
        tags=["users"],
        responses={
            201: OpenApiResponse(description="User successfully created"),
            400: OpenApiResponse(description="Validation error"),
        },
    ),
    retrieve=extend_schema(
        operation_id="users_retrieve",
        summary="Get user details",
        description="Get detailed information about a specific user",
        tags=["users"],
        responses={
            200: OpenApiResponse(description="Detailed user information"),
            404: OpenApiResponse(description="User not found"),
        },
    ),
    update=extend_schema(
        operation_id="users_update",
        summary="Update user",
        description="Update user information",
        tags=["users"],
        responses={
            200: OpenApiResponse(description="User successfully updated"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="User not found"),
        },
    ),
    partial_update=extend_schema(
        operation_id="users_partial_update",
        summary="Partially update user",
        description="Partially update user information",
        tags=["users"],
        responses={
            200: OpenApiResponse(description="User successfully updated"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="User not found"),
        },
    ),
    destroy=extend_schema(
        operation_id="users_destroy",
        summary="Delete user",
        description="Delete a user account",
        tags=["users"],
        responses={
            204: OpenApiResponse(description="User successfully deleted"),
            404: OpenApiResponse(description="User not found"),
        },
    ),
)
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User management with comprehensive filtering and search.
    Provides CRUD operations for User model with advanced query capabilities.
    Requires admin access and OAuth2 read/write scope.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedOrTokenHasScope]
    required_scopes = ["users"]

    # Filter configuration matching books/views.py pattern
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "is_active": ["exact"],
        "is_staff": ["exact"],
        "is_superuser": ["exact"],
        "date_joined": ["gte", "lte"],
        "last_login": ["gte", "lte"],
        "groups__name": ["icontains"],
    }
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["username", "email", "date_joined", "last_login", "first_name", "last_name"]
    ordering = ["username"]

    def get_queryset(self):
        """Return users with group information prefetched."""
        return User.objects.all().prefetch_related("groups")

    def get_serializer_class(self):
        """Use detailed serializer for retrieve actions."""
        if self.action == "retrieve":
            return UserDetailSerializer
        return UserSerializer

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="Recently joined users",
                response={
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer", "description": "Number of recent users"},
                        "recent_users": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/User"},
                            "description": "List of recently joined users",
                        },
                    },
                },
            )
        },
        description="Get the 10 most recently joined users in the system",
    )
    @action(detail=False, methods=["get"])
    def recent(self, request):
        """Get recently joined users."""
        recent_users = self.get_queryset().order_by("-date_joined")[:10]
        serializer = self.get_serializer(recent_users, many=True)
        return Response({"count": len(serializer.data), "recent_users": serializer.data})


@extend_schema_view(
    list=extend_schema(
        operation_id="groups_list",
        summary="List all groups",
        description="List all groups with filtering and search capabilities",
        tags=["groups"],
        responses={
            200: OpenApiResponse(description="Paginated list of user groups"),
        },
    ),
    retrieve=extend_schema(
        operation_id="groups_retrieve",
        summary="Get group details",
        description="Get detailed information about a specific group",
        tags=["groups"],
        responses={
            200: OpenApiResponse(description="Detailed group information with user count"),
            404: OpenApiResponse(description="Group not found"),
        },
    ),
)
class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Group management with comprehensive filtering and search.
    Provides read-only operations for Group model with advanced query capabilities.
    Requires admin access and OAuth2 'groups' scope.
    """

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticatedOrTokenHasScope]
    required_scopes = ["groups"]

    # Filter configuration matching books/views.py pattern
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["name"]
    search_fields = ["name"]
    ordering_fields = ["name"]
    ordering = ["name"]

    def get_queryset(self):
        """Return groups with user information prefetched."""
        return Group.objects.all().prefetch_related("user_set")

    @extend_schema(
        responses={
            200: OpenApiResponse(
                description="Users in the specified group",
                response={
                    "type": "object",
                    "properties": {
                        "group": {"type": "string", "description": "Group name"},
                        "user_count": {"type": "integer", "description": "Number of users in group"},
                        "users": {"type": "array", "items": {"$ref": "#/components/schemas/User"}, "description": "List of users in this group"},
                    },
                },
            )
        },
        description="Get all users that belong to this group",
    )
    @action(detail=True, methods=["get"])
    def users(self, request, pk=None):
        """Get users in this group."""
        group = self.get_object()
        users = group.user_set.all()
        serializer = UserSerializer(users, many=True)
        return Response({"group": group.name, "user_count": users.count(), "users": serializer.data})
