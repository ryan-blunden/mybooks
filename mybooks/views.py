from django.conf import settings
from django.contrib.auth.models import Group, User
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from oauth2_provider.contrib.rest_framework import TokenHasReadWriteScope, TokenHasScope
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response


def oauth_metadata(request):
    """Provide OAuth2 provider metadata."""
    return {
        "issuer": settings.SITE_URL,
        "authorization_endpoint": f"{settings.SITE_URL}/oauth/authorize",
        "token_endpoint": f"{settings.SITE_URL}/oauth/token",
        "registration_endpoint": f"{settings.SITE_URL}/oauth/register",
        "scopes_supported": ["org:read", "project:write", "team:write", "event:write"],
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
        "revocation_endpoint": f"{settings.SITE_URL}/oauth/token",
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
    list=extend_schema(description="List all users with filtering and search capabilities"),
    create=extend_schema(description="Create a new user account"),
    retrieve=extend_schema(description="Get detailed information about a specific user"),
    update=extend_schema(description="Update user information"),
    partial_update=extend_schema(description="Partially update user information"),
    destroy=extend_schema(description="Delete a user account"),
)
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User management with comprehensive filtering and search.
    Provides CRUD operations for User model with advanced query capabilities.
    Requires admin access and OAuth2 read/write scope.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser, TokenHasReadWriteScope]

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
            200: {
                "type": "object",
                "description": "User statistics across the system",
                "properties": {
                    "total_users": {"type": "integer", "description": "Total number of users"},
                    "active_users": {"type": "integer", "description": "Number of active users"},
                    "inactive_users": {"type": "integer", "description": "Number of inactive users"},
                    "staff_users": {"type": "integer", "description": "Number of staff users"},
                    "superusers": {"type": "integer", "description": "Number of superusers"},
                },
            }
        },
        description="Get comprehensive user statistics including counts by status and permissions",
    )
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get user statistics."""
        queryset = self.get_queryset()

        total_users = queryset.count()
        active_users = queryset.filter(is_active=True).count()
        staff_users = queryset.filter(is_staff=True).count()
        superusers = queryset.filter(is_superuser=True).count()

        return Response(
            {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": total_users - active_users,
                "staff_users": staff_users,
                "superusers": superusers,
                "regular_users": active_users - staff_users,
            }
        )

    @extend_schema(
        responses={
            200: {
                "type": "object",
                "description": "Recently joined users",
                "properties": {
                    "count": {"type": "integer", "description": "Number of recent users"},
                    "recent_users": {"type": "array", "items": {"$ref": "#/components/schemas/User"}, "description": "List of recently joined users"},
                },
            }
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
    list=extend_schema(description="List all groups with filtering and search capabilities"),
    retrieve=extend_schema(description="Get detailed information about a specific group"),
)
class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Group management with comprehensive filtering and search.
    Provides read-only operations for Group model with advanced query capabilities.
    Requires admin access and OAuth2 'groups' scope.
    """

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser, TokenHasScope]
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
            200: {
                "type": "object",
                "description": "Users in the specified group",
                "properties": {
                    "group": {"type": "string", "description": "Group name"},
                    "user_count": {"type": "integer", "description": "Number of users in group"},
                    "users": {"type": "array", "items": {"$ref": "#/components/schemas/User"}, "description": "List of users in this group"},
                },
            }
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

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get group statistics."""
        queryset = self.get_queryset()

        total_groups = queryset.count()
        groups_with_users = queryset.filter(user_set__isnull=False).distinct().count()
        empty_groups = total_groups - groups_with_users

        return Response({"total_groups": total_groups, "groups_with_users": groups_with_users, "empty_groups": empty_groups})
