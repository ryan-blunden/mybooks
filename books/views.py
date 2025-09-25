from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter

from .models import Author, Book, Review, UserBook
from .serializers import (
    AuthorDetailSerializer,
    AuthorSerializer,
    BookSerializer,
    GenreSerializer,
    ReviewSerializer,
    UserBookDetailSerializer,
    UserBookSerializer,
)


@extend_schema_view(
    list=extend_schema(
        operation_id="list_authors_for_discovery",
        summary="List all authors for book discovery",
        description="Retrieve a paginated list of all authors in the book system for discovery and exploration purposes. This endpoint returns basic author information including their name, biography snippet, and total book count. Use this tool when you need to help users discover authors or browse the author catalog. Each author entry includes a book count to help users understand the author's presence in the system. The response is paginated and includes authors sorted alphabetically by name. This is a read-only endpoint that requires user authentication but does not filter by user's personal collection - it shows all authors in the system regardless of whether the user has their books in their collection.",
        parameters=[
            OpenApiParameter(
                name="search",
                description="Search authors by name or biography content. Performs case-insensitive text search across author names and biographical information. Use this to find specific authors or authors with particular expertise mentioned in their biography.",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="ordering",
                description="Sort the author list by specified field. Available options: 'name' (alphabetical), 'created_at' (newest first), '-name' (reverse alphabetical), '-created_at' (oldest first). Default is alphabetical by name.",
                required=False,
                type=str,
                enum=["name", "-name", "created_at", "-created_at"],
            ),
        ],
        tags=["authors"],
        responses={
            200: OpenApiResponse(description="A paginated list of authors with basic info and book counts"),
        },
    ),
    retrieve=extend_schema(
        operation_id="get_author_complete_details",
        summary="Get complete author information and book list",
        description="Retrieve comprehensive information about a specific author by their unique author_id, including their complete biography and full list of books they've written. This endpoint returns detailed author information along with all books by this author available in the system. Use this tool when you need complete information about a specific author, such as when a user wants to explore all works by a particular author or needs detailed biographical information. The response includes the author's full biography, profile image if available, and a complete list of their books with titles, genres, and publication metadata. This does not show user-specific information like reading status - for that, use the user collection endpoints. Requires authentication and returns a 404 error if the author_id doesn't exist.",
        tags=["authors"],
        responses={
            200: OpenApiResponse(description="Complete author details with full book catalog"),
            404: OpenApiResponse(description="Author not found for the provided author_id"),
        },
    ),
)
class AuthorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Author management with read-only operations.

    Authors are created automatically when adding books to the system.
    This endpoint provides browsing and discovery of authors and their works.
    """

    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [IsAuthenticatedOrTokenHasScope]
    required_scopes = ["read"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "biography"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        """Use detailed serializer for retrieve actions."""
        if self.action == "retrieve":
            return AuthorDetailSerializer
        return AuthorSerializer


@extend_schema_view(
    list=extend_schema(
        operation_id="list_user_personal_book_collection",
        summary="List authenticated user's personal book collection",
        description="Retrieve all books in the authenticated user's personal collection with reading status tracking and date information. This endpoint returns only books that the authenticated user has explicitly added to their personal library, along with their reading status (want_to_read, reading, finished, dropped), dates when books were added/started/finished, and associated book details. Use this tool when you need to see what books a user has in their collection, check reading progress, or manage their personal library. The response includes book metadata (title, author, genre) combined with user-specific data (reading status, dates). This is different from browsing all available books - this shows only books the user has chosen to track. Results are paginated and sorted by date_added (most recent first). Requires user authentication.",
        parameters=[
            OpenApiParameter(
                name="search",
                description="Search within user's collection by book title, author name, or reading status. Performs case-insensitive text search to help find specific books in the user's personal library.",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="ordering",
                description="Sort the collection by specified field. Available options: 'date_added' (newest first), 'book__title' (alphabetical), 'reading_status', 'date_started', 'date_finished', or negative versions for reverse order. Default is newest added first (-date_added).",
                required=False,
                type=str,
                enum=[
                    "date_added",
                    "-date_added",
                    "book__title",
                    "-book__title",
                    "reading_status",
                    "-reading_status",
                    "date_started",
                    "-date_started",
                    "date_finished",
                    "-date_finished",
                ],
            ),
        ],
        tags=["user-books", "collection"],
        responses={
            200: OpenApiResponse(description="Paginated list of books in user's personal collection with reading status"),
        },
    ),
    create=extend_schema(
        operation_id="add_book_to_user_collection",
        summary="Add a book to user's personal collection",
        description="Add a book to the authenticated user's personal collection with initial reading status. You can either reference an existing book by its book_id or create a completely new book entry if it doesn't exist in the system yet. When adding an existing book, provide the book_id and desired reading_status (defaults to 'want_to_read'). When creating a new book, provide complete book details including title, author information, and genre. Use this tool when a user wants to add a book to their personal library for tracking. The system prevents duplicate entries - each user can only have one instance of each book in their collection. The response includes the created UserBook relationship with book details and initial status. This creates a tracking relationship but doesn't modify the original book record if using an existing book. Requires user authentication.",
        tags=["user-books", "collection"],
        responses={
            201: OpenApiResponse(description="Book successfully added to user's collection with initial reading status"),
            400: OpenApiResponse(description="Validation error, missing required fields, or book already exists in user's collection"),
        },
    ),
    retrieve=extend_schema(
        operation_id="get_book_from_user_collection",
        summary="Get detailed information about a book in user's collection",
        description="Retrieve comprehensive information about a specific book in the authenticated user's personal collection using the userbook_id (not the book_id). This endpoint returns the user's relationship to the book including current reading status, dates when the book was added/started/finished, combined with complete book details (title, author, description, genre) and any review the user has written for this book. Use this tool when you need detailed information about how a specific user relates to a specific book in their collection. The userbook_id is the unique identifier for the user-book relationship, which you can get from the list endpoint. This is different from the general book browsing endpoint - this shows user-specific tracking information. Returns 404 if the userbook_id doesn't exist or doesn't belong to the authenticated user. Requires user authentication.",
        tags=["user-books", "collection"],
        responses={
            200: OpenApiResponse(description="Complete book details with user's reading status, dates, and review if available"),
            404: OpenApiResponse(description="UserBook relationship not found in authenticated user's collection"),
        },
    ),
    update=extend_schema(
        operation_id="update_book_reading_status_in_collection",
        summary="Update reading status and tracking for book in user's collection",
        description="Update the reading status and tracking information for a book in the authenticated user's collection using the userbook_id. This endpoint allows changing the reading_status (want_to_read, reading, finished, dropped) and automatically manages related date fields based on status transitions. When status changes to 'reading', date_started is set to current time. When status changes to 'finished', date_finished is set to current time. Use this tool when a user progresses through reading a book or changes their intent for a book in their collection. The userbook_id identifies the specific user-book relationship to update. You cannot change which book this relationship points to - only the user's interaction with that book. The system validates status transitions and ensures dates remain consistent. Requires the complete object data (PUT method). PATCH method is not supported due to technical issues - use PUT for all updates. Requires user authentication and ownership of the userbook relationship.",
        tags=["user-books", "collection"],
        responses={
            200: OpenApiResponse(description="Book reading status successfully updated with automatic date management"),
            400: OpenApiResponse(description="Validation error or invalid status transition"),
            404: OpenApiResponse(description="UserBook relationship not found in authenticated user's collection"),
        },
    ),
    destroy=extend_schema(
        operation_id="remove_book_from_user_collection",
        summary="Remove book from user's personal collection",
        description="Remove a book from the authenticated user's personal collection using the userbook_id. This operation deletes the user-book relationship and all associated tracking data (reading status, dates) but does NOT delete the book itself from the system - other users can still have this book in their collections and the book remains available for browsing and future additions. Use this tool when a user wants to completely remove a book from their personal library and stop tracking it. This action also removes any review the user has written for this book, as reviews are tied to the user-book relationship. The userbook_id identifies the specific relationship to delete. This is irreversible - if the user wants the book back in their collection, they'll need to add it again with a fresh tracking relationship. Requires user authentication and ownership of the userbook relationship.",
        tags=["user-books", "collection"],
        responses={
            204: OpenApiResponse(description="Book and all tracking data successfully removed from user's collection"),
            404: OpenApiResponse(description="UserBook relationship not found in authenticated user's collection"),
        },
    ),
)
class UserBookViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing books in the user's personal collection.

    Provides full CRUD operations for books in the authenticated user's library,
    including reading status tracking and automatic date management.

    Note: PATCH is disabled due to hanging issues with the development server.
    Use PUT for updates instead.
    """

    serializer_class = UserBookSerializer
    permission_classes = [IsAuthenticatedOrTokenHasScope]
    required_scopes = ["write"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["reading_status"]
    search_fields = ["book__title", "book__author__name", "reading_status"]
    ordering_fields = ["date_added", "date_started", "date_finished", "book__title", "reading_status"]
    ordering = ["-date_added"]
    http_method_names = ["get", "post", "put", "delete", "head", "options"]  # Exclude 'patch'

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
    list=extend_schema(
        operation_id="list_user_book_reviews",
        summary="List all reviews written by authenticated user",
        description="Retrieve all book reviews that the authenticated user has written, including ratings, review text, and associated book information. This endpoint returns only reviews created by the authenticated user, not reviews by other users or reviews for books not in the user's collection. Each review includes the star rating (1-5), review text content, creation/update timestamps, and complete details about the book being reviewed (title, author, genre). Use this tool when you need to see all reviews a user has written, for displaying their review history, or for managing their review content. Reviews are automatically linked to books in the user's collection - users can only review books they have added to their personal library. Results are paginated and sorted by creation date (most recent first). Requires user authentication.",
        parameters=[
            OpenApiParameter(
                name="search",
                description="Search within user's reviews by book title, author name, or review text content. Performs case-insensitive text search to help find specific reviews in the user's review history.",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="ordering",
                description="Sort reviews by specified field. Available options: 'created_at' (newest first), 'updated_at', 'rating' (highest first), 'book__title' (alphabetical), or negative versions for reverse order. Default is newest created first (-created_at).",
                required=False,
                type=str,
                enum=["created_at", "-created_at", "updated_at", "-updated_at", "rating", "-rating", "book__title", "-book__title"],
            ),
        ],
        tags=["reviews"],
        responses={
            200: OpenApiResponse(description="Paginated list of all reviews written by the authenticated user"),
        },
    ),
    create=extend_schema(
        operation_id="create_book_review",
        summary="Write a new review for a book in user's collection",
        description="Create a new review for a book that exists in the authenticated user's personal collection. The review must include a star rating (integer from 1-5) and can optionally include review text content. Users can only write one review per book - attempting to create a duplicate review will result in a validation error. The book being reviewed must already exist in the user's collection (added via the user_books endpoints). Use this tool when a user wants to rate and review a book they have read or are reading. The review becomes part of the book's overall review collection and is associated with both the user and the specific book. Reviews can be edited later using the update endpoints. The system validates that the rating is within the 1-5 range and that the user hasn't already reviewed this book. Requires user authentication and the book must be in the user's collection.",
        tags=["reviews"],
        responses={
            201: OpenApiResponse(description="Review successfully created with rating and optional text"),
            400: OpenApiResponse(description="Validation error, invalid rating, or user has already reviewed this book"),
        },
    ),
    retrieve=extend_schema(
        operation_id="get_user_review_details",
        summary="Get detailed information about a specific user review",
        description="Retrieve complete information about a specific review written by the authenticated user using the review_id. This endpoint returns the full review details including the star rating, complete review text, creation and last update timestamps, and comprehensive information about the book being reviewed (title, author, genre, description). Use this tool when you need detailed information about a specific review, such as when editing a review or displaying full review content. The review_id must correspond to a review written by the authenticated user - users cannot access reviews written by other users through this endpoint. The response includes both the review data and associated book metadata for context. Returns 404 if the review_id doesn't exist or doesn't belong to the authenticated user. Requires user authentication.",
        tags=["reviews"],
        responses={
            200: OpenApiResponse(description="Complete review details with associated book information"),
            404: OpenApiResponse(description="Review not found or not owned by authenticated user"),
        },
    ),
    update=extend_schema(
        operation_id="update_user_book_review",
        summary="Update an existing book review with complete data",
        description="Update an existing review written by the authenticated user using the review_id. This endpoint allows modification of the star rating (1-5) and review text content, but the associated book cannot be changed once a review is created - to review a different book, create a new review. Use this tool when a user wants to change their opinion about a book, update their rating, or revise their review text. The update automatically sets the updated_at timestamp to the current time. Requires the complete review data (PUT method) including both rating and text fields. For partial updates (changing only rating or only text), use the partial_update endpoint instead. The review_id must correspond to a review owned by the authenticated user. Validates that the new rating is within the 1-5 range. Requires user authentication and ownership of the review.",
        tags=["reviews"],
        responses={
            200: OpenApiResponse(description="Review successfully updated with new rating and/or text content"),
            400: OpenApiResponse(description="Validation error or invalid rating value"),
            404: OpenApiResponse(description="Review not found or not owned by authenticated user"),
        },
    ),
    partial_update=extend_schema(
        operation_id="partially_update_user_review",
        summary="Partially update specific fields of a book review",
        description="Partially update an existing review by modifying only the fields you specify (typically rating or text) without requiring the complete review data. This endpoint allows updating just the star rating, just the review text, or both, without needing to provide all fields. The associated book cannot be changed. Use this tool when you want to make targeted changes to a review, such as adjusting only the rating or only the text content. The update automatically sets the updated_at timestamp. More convenient than the full update endpoint when you only need to change specific fields. The review_id must correspond to a review owned by the authenticated user. Validates that any provided rating is within the 1-5 range. The book association remains unchanged. Requires user authentication and ownership of the review.",
        tags=["reviews"],
        responses={
            200: OpenApiResponse(description="Review fields successfully updated with automatic timestamp management"),
            400: OpenApiResponse(description="Validation error or invalid field values"),
            404: OpenApiResponse(description="Review not found or not owned by authenticated user"),
        },
    ),
    destroy=extend_schema(
        operation_id="delete_user_book_review",
        summary="Permanently delete a book review",
        description="Permanently delete a review written by the authenticated user using the review_id. This operation completely removes the review from the system including the rating, text content, and all associated metadata. The action is irreversible - if the user wants to review the book again, they will need to create a completely new review. Use this tool when a user no longer wants their review to be part of the book's review collection or wants to remove their opinion from the system. This does not affect the book itself or the user's collection relationship to the book - it only removes the review. The book remains in the user's collection with whatever reading status it had. The review_id must correspond to a review owned by the authenticated user. Requires user authentication and ownership of the review.",
        tags=["reviews"],
        responses={
            204: OpenApiResponse(description="Review permanently deleted from the system"),
            404: OpenApiResponse(description="Review not found or not owned by authenticated user"),
        },
    ),
)
class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user book reviews.

    Provides full CRUD operations for reviews, with automatic user scoping
    and validation to ensure users can only review books once.
    """

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrTokenHasScope]
    required_scopes = ["write"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["rating"]
    search_fields = ["book__title", "book__author__name", "text"]
    ordering_fields = ["created_at", "updated_at", "rating", "book__title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Return only reviews for the authenticated user."""
        # Handle schema generation with fake view
        if getattr(self, "swagger_fake_view", False):
            return Review.objects.none()
        return Review.objects.filter(user=self.request.user).select_related("book", "book__author")


@extend_schema_view(
    list=extend_schema(
        operation_id="browse_all_available_books",
        summary="Browse and discover all books available in the system",
        description="Browse through the complete catalog of all books available in the system for discovery and exploration purposes. This endpoint returns all books that exist in the system regardless of whether they are in any user's personal collection. Each book entry includes basic information like title, author name, genre, tagline, and creation date. Use this tool when users want to discover new books to potentially add to their collection, search for specific titles or authors, or explore the complete book catalog. This is different from the user collection endpoints - this shows the master catalog of all available books, not user-specific collection data. The response does not include user-specific information like reading status or personal notes. Results are paginated and sorted alphabetically by title. Use the book_id from this response to add books to a user's collection via the user_books endpoints. Requires user authentication for access.",
        parameters=[
            OpenApiParameter(
                name="search",
                description="Search books by title, description, tagline, or author name. Performs case-insensitive text search across book titles, descriptions, taglines, and author names. Use this to find specific books, books by particular authors, or books containing certain keywords in their descriptions.",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="ordering",
                description="Sort the book list by specified field. Available options: 'title' (alphabetical), 'created_at' (newest first), 'author__name' (by author name), or negative versions for reverse order ('-title', '-created_at', '-author__name'). Default is alphabetical by title.",
                required=False,
                type=str,
                enum=["title", "-title", "created_at", "-created_at", "author__name", "-author__name"],
            ),
        ],
        tags=["books", "browse"],
        responses={
            200: OpenApiResponse(description="Paginated catalog of all books available for discovery and collection"),
        },
    ),
    retrieve=extend_schema(
        operation_id="get_book_catalog_details",
        summary="Get comprehensive details about a specific book from the catalog",
        description="Retrieve complete information about a specific book from the system catalog using the book_id. This endpoint returns detailed book information including title, complete description, author biographical information, genre, tagline, cover image, and publication metadata. Use this tool when you need comprehensive information about a book for display, decision-making about adding it to a collection, or providing detailed book information to users. This shows the master book record with all available metadata but does not include user-specific information like reading status or personal reviews - for that information, use the user collection endpoints. The book_id can be obtained from the book browsing endpoint or from user collection responses. Returns comprehensive author details embedded within the book information. Returns 404 if the book_id doesn't exist in the system. Requires user authentication.",
        tags=["books", "browse"],
        responses={
            200: OpenApiResponse(description="Complete book information with author details and metadata"),
            404: OpenApiResponse(description="Book not found in the system catalog"),
        },
    ),
)
class BookViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for browsing and discovering books.

    Provides book discovery functionality for users to find books
    they want to add to their personal collections.
    """

    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [IsAuthenticatedOrTokenHasScope]
    required_scopes = ["read"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["genre"]
    search_fields = ["title", "description", "tagline", "author__name"]
    ordering_fields = ["title", "created_at", "author__name"]
    ordering = ["title"]

    def get_queryset(self):
        """Return all books with author information."""
        return Book.objects.all().select_related("author")


@extend_schema_view(
    list=extend_schema(
        operation_id="list_available_book_genres",
        summary="List all available book genres with metadata",
        description="Retrieve a comprehensive list of all book genres available in the system with statistical information. This endpoint returns each genre with its identifier, human-readable name, total book count, and optional descriptive information. Use this tool when you need to display genre categories for filtering, show users what types of books are available, or provide genre selection options for book discovery and collection management. Each genre entry includes the total number of books currently available in that category, helping users understand the breadth of content in each genre. The response includes all predefined genres supported by the system regardless of whether books currently exist in each category. Results are sorted alphabetically by genre name for consistent presentation. This is a read-only endpoint that provides system-wide genre information and requires user authentication for access.",
        parameters=[
            OpenApiParameter(
                name="search",
                description="Search genres by name or description content. Performs case-insensitive text search across genre names and descriptions to help find specific genre categories. Use this to locate particular genres or genres with specific characteristics mentioned in their descriptions.",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="ordering",
                description="Sort the genre list by specified field. Available options: 'name' (alphabetical), 'book_count' (most books first), '-name' (reverse alphabetical), '-book_count' (fewest books first). Default is alphabetical by name for consistent browsing experience.",
                required=False,
                type=str,
                enum=["name", "-name", "book_count", "-book_count"],
            ),
        ],
        tags=["genres", "metadata"],
        responses={
            200: OpenApiResponse(description="Complete list of book genres with book counts and metadata"),
        },
    ),
    retrieve=extend_schema(
        operation_id="get_genre_details_and_statistics",
        summary="Get detailed information about a specific genre",
        description="Retrieve comprehensive information about a specific book genre using the genre identifier (slug). This endpoint returns detailed genre information including the human-readable name, complete description, total book count, and statistical metadata about books in this category. Use this tool when you need detailed information about a specific genre, such as when displaying genre-specific pages, providing genre descriptions to users, or showing detailed statistics about book categories. The genre_id should be the slug format identifier (e.g., 'science_fiction', 'fantasy', 'historical_fiction'). The response includes comprehensive metadata about the genre and its usage within the book collection system. Returns 404 if the genre_id doesn't correspond to a valid genre supported by the system. This does not return the actual books in the genre - for that, use the book browsing endpoints with genre filtering. Requires user authentication.",
        tags=["genres", "metadata"],
        responses={
            200: OpenApiResponse(description="Detailed genre information with statistics and metadata"),
            404: OpenApiResponse(description="Genre not found - invalid genre identifier provided"),
        },
    ),
)
class GenreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for browsing and discovering book genres.

    Provides genre discovery functionality with statistical information
    to help users understand available book categories and their usage.
    """

    serializer_class = GenreSerializer
    permission_classes = [IsAuthenticatedOrTokenHasScope]
    required_scopes = ["read"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "book_count"]
    ordering = ["name"]

    def get_queryset(self):
        """Return genre data with book counts."""

        # Create genre objects with book counts
        genres = []
        for genre_id, genre_name in Book.GENRE_CHOICES:
            book_count = Book.objects.filter(genre=genre_id).count()

            # Add basic descriptions for some genres
            descriptions = {
                "fantasy": "Stories featuring magical elements, mythical creatures, and imaginary worlds",
                "science_fiction": "Speculative fiction dealing with futuristic concepts and advanced technology",
                "mystery": "Stories involving puzzles, crimes, or unexplained events to be solved",
                "romance": "Stories focusing on romantic relationships and emotional connections",
                "horror": "Stories designed to frighten, unsettle, or create suspense",
                "biography": "Non-fiction accounts of real people's lives and experiences",
                "history": "Non-fiction works about past events, cultures, and civilizations",
                "science": "Educational works about scientific discoveries, theories, and research",
                "philosophy": "Works exploring fundamental questions about existence, knowledge, and ethics",
                "fiction": "Narrative literature featuring imaginary characters and events",
            }

            genre_obj = {"id": genre_id, "name": genre_name, "book_count": book_count, "description": descriptions.get(genre_id, "")}
            genres.append(genre_obj)

        return genres

    def list(self, request, *args, **kwargs):
        """List all genres with filtering and search capabilities."""
        from rest_framework import status as http_status
        from rest_framework.response import Response

        queryset = self.get_queryset()

        # Apply search filtering
        search = request.query_params.get("search", "").lower()
        if search:
            queryset = [genre for genre in queryset if search in genre["name"].lower() or search in genre["description"].lower()]

        # Apply ordering
        ordering = request.query_params.get("ordering", "name")
        reverse = ordering.startswith("-")
        order_field = ordering.lstrip("-")

        if order_field in ["name", "book_count"]:
            queryset = sorted(queryset, key=lambda x: x[order_field], reverse=reverse)

        # Serialize data
        serializer = self.get_serializer(queryset, many=True)

        # Return paginated response matching DRF format
        return Response({"count": len(serializer.data), "next": None, "previous": None, "results": serializer.data}, status=http_status.HTTP_200_OK)

    def retrieve(self, request, pk=None, *args, **kwargs):
        """Retrieve specific genre by ID."""
        from rest_framework import status as http_status
        from rest_framework.exceptions import NotFound
        from rest_framework.response import Response

        queryset = self.get_queryset()

        # Find genre by ID
        genre_obj = None
        for genre in queryset:
            if genre["id"] == pk:
                genre_obj = genre
                break

        if not genre_obj:
            raise NotFound("Genre not found")

        serializer = self.get_serializer(genre_obj)
        return Response(serializer.data, status=http_status.HTTP_200_OK)
