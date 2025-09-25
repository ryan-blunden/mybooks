from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets

from .models import Author, Book, Review, UserBook
from .serializers import AuthorDetailSerializer, AuthorSerializer, BookSerializer, ReviewSerializer, UserBookDetailSerializer, UserBookSerializer


@extend_schema_view(
    list=extend_schema(description="List all authors"),
    retrieve=extend_schema(description="Get detailed information about a specific author including books"),
)
class AuthorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Author with list/retrieve operations.
    Read-only as authors are created automatically via book creation.
    """

    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Use detailed serializer for retrieve actions."""
        if self.action == "retrieve":
            return AuthorDetailSerializer
        return AuthorSerializer


@extend_schema_view(
    list=extend_schema(description="List books in user's personal collection"),
    create=extend_schema(description="Add a book to user's collection"),
    retrieve=extend_schema(description="Get detailed information about a book in user's collection"),
    update=extend_schema(description="Update reading status and notes for a book"),
    partial_update=extend_schema(description="Partially update book information in collection"),
    destroy=extend_schema(description="Remove a book from user's collection"),
)
class UserBookViewSet(viewsets.ModelViewSet):
    """
    ViewSet for UserBook with CRUD operations.
    Represents books in user's personal collection.
    """

    serializer_class = UserBookSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only books for the authenticated user."""
        # Handle schema generation with fake view
        if getattr(self, "swagger_fake_view", False):
            return UserBook.objects.none()
        return UserBook.objects.filter(user=self.request.user).select_related("book", "book__author")

    def get_serializer_class(self):
        """Use detailed serializer for retrieve actions."""
        if self.action == "retrieve":
            return UserBookDetailSerializer
        return UserBookSerializer


@extend_schema_view(
    list=extend_schema(description="List user's book reviews"),
    create=extend_schema(description="Create a new book review"),
    retrieve=extend_schema(description="Get detailed information about a specific review"),
    update=extend_schema(description="Update a book review"),
    partial_update=extend_schema(description="Partially update a book review"),
    destroy=extend_schema(description="Delete a book review"),
)
class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Review with user-scoped CRUD operations.
    Users can only access their own reviews.
    """

    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only reviews for the authenticated user."""
        # Handle schema generation with fake view
        if getattr(self, "swagger_fake_view", False):
            return Review.objects.none()
        return Review.objects.filter(user=self.request.user).select_related("book", "book__author")


# Additional ViewSet for Book browsing (not user-specific)
@extend_schema_view(
    list=extend_schema(description="Browse all books in the system"),
    retrieve=extend_schema(description="Get detailed information about a specific book"),
)
class BookViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for browsing all books in the system.
    Used for discovery and adding books to collection.
    """

    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return all books with author information."""
        return Book.objects.all().select_related("author")
