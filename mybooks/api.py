from django.contrib.auth.models import User, Group
from oauth2_provider.contrib.rest_framework import TokenHasScope, TokenHasReadWriteScope
from rest_framework import viewsets, permissions, serializers


# first we define the serializers
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ("name",)


# Create the API ViewSets
class UserViewSet(viewsets.ModelViewSet):
    """
    A ViewSet for managing users.
    Provides CRUD operations for User model.
    Requires staff access.
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser, TokenHasReadWriteScope]
    queryset = User.objects.all()
    serializer_class = UserSerializer


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    A ViewSet for viewing groups.
    Provides read-only operations for Group model.
    Requires OAuth2 'groups' scope and staff access.
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser, TokenHasScope]
    required_scopes = ["groups"]
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
