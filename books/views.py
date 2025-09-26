from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

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
        summary="List authors",
        description="Retrieve a paginated list of all authors with search and ordering support.",
        parameters=[
            OpenApiParameter(
                name="search",
                description="Search authors by name or biography (case-insensitive).",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="ordering",
                description="Sort results by 'name', '-name', 'created_at', or '-created_at'.",
                required=False,
                type=str,
                enum=["name", "-name", "created_at", "-created_at"],
            ),
        ],
        tags=["authors"],
        responses={
            200: OpenApiResponse(description="Paginated list of authors"),
        },
    ),
    retrieve=extend_schema(
        operation_id="get_author_complete_details",
        summary="Retrieve author",
        description="Get full author details and their books.",
        tags=["authors"],
        responses={
            200: OpenApiResponse(description="Author details returned"),
            404: OpenApiResponse(description="Author not found"),
        },
    ),
    create=extend_schema(
        operation_id="create_author",
        summary="Create author",
        description="Create a new author record for use when cataloging books.",
        tags=["authors"],
        responses={
            201: OpenApiResponse(description="Author created"),
            400: OpenApiResponse(description="Validation error"),
        },
    ),
    update=extend_schema(
        operation_id="update_author",
        summary="Update author",
        description="Replace all author fields with supplied data.",
        tags=["authors"],
        responses={
            200: OpenApiResponse(description="Author updated"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Author not found"),
        },
    ),
    partial_update=extend_schema(
        operation_id="partial_update_author",
        summary="Partially update author",
        description="Update selected author fields without replacing the entire record.",
        tags=["authors"],
        responses={
            200: OpenApiResponse(description="Author partially updated"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Author not found"),
        },
    ),
    destroy=extend_schema(
        operation_id="delete_author",
        summary="Delete author",
        description="Delete an author. Cascades to books that reference this author.",
        tags=["authors"],
        responses={
            204: OpenApiResponse(description="Author deleted"),
            404: OpenApiResponse(description="Author not found"),
        },
    ),
)
class AuthorViewSet(viewsets.ModelViewSet):
    """
    Full CRUD ViewSet for managing authors in the catalog.

    Supports author discovery, direct author maintenance, and feeds
    creation flows in the book catalog.
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
        tags=["user-books"],
        responses={
            200: OpenApiResponse(description="Paginated list of books in user's personal collection with reading status"),
        },
    ),
    create=extend_schema(
        operation_id="add_book_to_user_collection",
        summary="Add a book to user's personal collection",
        description="Add a book to the authenticated user's personal collection with initial reading status. You can either reference an existing book by its book_id or create a completely new book entry if it doesn't exist in the system yet. When adding an existing book, provide the book_id and desired reading_status (defaults to 'want_to_read'). When creating a new book, provide complete book details including title, author information, and genre. Use this tool when a user wants to add a book to their personal library for tracking. The system prevents duplicate entries - each user can only have one instance of each book in their collection. The response includes the created UserBook relationship with book details and initial status. This creates a tracking relationship but doesn't modify the original book record if using an existing book. Requires user authentication.",
        tags=["user-books"],
        responses={
            201: OpenApiResponse(description="Book successfully added to user's collection with initial reading status"),
            400: OpenApiResponse(description="Validation error, missing required fields, or book already exists in user's collection"),
        },
    ),
    retrieve=extend_schema(
        operation_id="get_book_from_user_collection",
        summary="Get detailed information about a book in user's collection",
        description="Retrieve comprehensive information about a specific book in the authenticated user's personal collection using the userbook_id (not the book_id). This endpoint returns the user's relationship to the book including current reading status, dates when the book was added/started/finished, combined with complete book details (title, author, description, genre) and any review the user has written for this book. Use this tool when you need detailed information about how a specific user relates to a specific book in their collection. The userbook_id is the unique identifier for the user-book relationship, which you can get from the list endpoint. This is different from the general book browsing endpoint - this shows user-specific tracking information. Returns 404 if the userbook_id doesn't exist or doesn't belong to the authenticated user. Requires user authentication.",
        tags=["user-books"],
        responses={
            200: OpenApiResponse(description="Complete book details with user's reading status, dates, and review if available"),
            404: OpenApiResponse(description="UserBook relationship not found in authenticated user's collection"),
        },
    ),
    update=extend_schema(
        operation_id="update_book_reading_status_in_collection",
        summary="Update reading status and tracking for book in user's collection",
        description="Update the reading status and tracking information for a book in the authenticated user's collection using the userbook_id. This endpoint allows changing the reading_status (want_to_read, reading, finished, dropped) and automatically manages related date fields based on status transitions. When status changes to 'reading', date_started is set to current time. When status changes to 'finished', date_finished is set to current time. Use this tool when a user progresses through reading a book or changes their intent for a book in their collection. The userbook_id identifies the specific user-book relationship to update. You cannot change which book this relationship points to - only the user's interaction with that book. The system validates status transitions and ensures dates remain consistent. Requires the complete object data (PUT method). PATCH method is not supported due to technical issues - use PUT for all updates. Requires user authentication and ownership of the userbook relationship.",
        tags=["user-books"],
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
        tags=["user-books"],
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
        operation_id="search_available_books",
        summary="List books",
        description="Browse the full catalog of books with search, filtering, and ordering support.",
        parameters=[
            OpenApiParameter(
                name="search",
                description="Search by title, description, tagline, or author name.",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="ordering",
                description="Sort results by 'title', 'created_at', or 'author__name' (prefix with '-' to reverse).",
                required=False,
                type=str,
                enum=["title", "-title", "created_at", "-created_at", "author__name", "-author__name"],
            ),
        ],
        tags=["books"],
        responses={
            200: OpenApiResponse(description="Paginated list of catalog books"),
        },
    ),
    retrieve=extend_schema(
        operation_id="get_book_catalog_details",
        summary="Retrieve book",
        description="Get full catalog details for a specific book.",
        tags=["books"],
        responses={
            200: OpenApiResponse(description="Book details returned"),
            404: OpenApiResponse(description="Book not found"),
        },
    ),
    create=extend_schema(
        operation_id="create_book",
        summary="Create book",
        description="Create a new catalog book. Provide core metadata and author name (created on demand).",
        tags=["books"],
        responses={
            201: OpenApiResponse(description="Book created"),
            400: OpenApiResponse(description="Validation error"),
        },
    ),
    update=extend_schema(
        operation_id="update_book",
        summary="Update book",
        description="Replace a book's metadata, including author reassignment if desired.",
        tags=["books"],
        responses={
            200: OpenApiResponse(description="Book updated"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Book not found"),
        },
    ),
    partial_update=extend_schema(
        operation_id="partial_update_book",
        summary="Partially update book",
        description="Update selected book fields without replacing the entire record.",
        tags=["books"],
        responses={
            200: OpenApiResponse(description="Book partially updated"),
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Book not found"),
        },
    ),
    destroy=extend_schema(
        operation_id="delete_book",
        summary="Delete book",
        description="Delete a catalog book. Cascades to user collections and reviews tied to the book.",
        tags=["books"],
        responses={
            204: OpenApiResponse(description="Book deleted"),
            404: OpenApiResponse(description="Book not found"),
        },
    ),
)
class BookViewSet(viewsets.ModelViewSet):
    """
    Full CRUD ViewSet for the shared book catalog.

    Supports discovery, catalog maintenance, and integrations that
    need to manage the universe of available books.
    """

    # AIDEV-NOTE: Deleting catalog books cascades to user collections and reviews; confirm intent before bulk deletes.
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [IsAuthenticatedOrTokenHasScope]
    required_scopes = ["read"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["genre", "author__name"]
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
        parameters=[
            OpenApiParameter(
                name="id",
                description="Genre identifier (slug format, e.g. 'science_fiction', 'fantasy')",
                required=True,
                type=str,
                location=OpenApiParameter.PATH,
            ),
        ],
        tags=["genres", "metadata"],
        responses={
            200: OpenApiResponse(description="Detailed genre information with statistics and metadata"),
            404: OpenApiResponse(description="Genre not found - invalid genre identifier provided"),
        },
    ),
)
class GenreViewSet(viewsets.ViewSet):
    """
    ViewSet for browsing and discovering book genres.

    Provides genre discovery functionality with statistical information
    to help users understand available book categories and their usage.
    No backing model - generates genre data dynamically from Book.GENRE_CHOICES.
    """

    serializer_class = GenreSerializer
    permission_classes = [IsAuthenticatedOrTokenHasScope]
    required_scopes = ["read"]

    def get_serializer(self, *args, **kwargs):
        """Get serializer instance."""
        kwargs["context"] = self.get_serializer_context()
        return self.serializer_class(*args, **kwargs)

    def get_serializer_context(self):
        """Extra context provided to the serializer class."""
        return {"request": self.request, "format": self.format_kwarg, "view": self}

    def get_queryset(self):
        """Return genre data with book counts for all available genres."""

        # Create genre objects with book counts for ALL genre choices
        genres = []
        for genre_id, genre_name in Book.GENRE_CHOICES:
            book_count = Book.objects.filter(genre=genre_id).count()

            # Add basic descriptions for genres where helpful
            descriptions = {
                "art": "Visual arts, art history, and artistic techniques",
                "biography": "Non-fiction accounts of real people's lives and experiences",
                "business": "Business strategy, entrepreneurship, and professional development",
                "chick_lit": "Contemporary fiction targeting primarily female readership",
                "childrens": "Books specifically written for children and young readers",
                "christian": "Religious and spiritual content from Christian perspective",
                "classics": "Timeless literature of enduring significance and quality",
                "comics": "Sequential art storytelling in comic book format",
                "contemporary": "Modern fiction reflecting current times and issues",
                "cookbooks": "Recipes, cooking techniques, and culinary arts",
                "crime": "Stories involving criminal activity and law enforcement",
                "ebooks": "Digital books and electronic publications",
                "fantasy": "Stories featuring magical elements, mythical creatures, and imaginary worlds",
                "fiction": "Narrative literature featuring imaginary characters and events",
                "gay_and_lesbian": "Literature exploring LGBTQ+ themes and experiences",
                "graphic_novels": "Extended comic book narratives with literary depth",
                "historical_fiction": "Fiction set in the past, recreating historical periods",
                "history": "Non-fiction works about past events, cultures, and civilizations",
                "horror": "Stories designed to frighten, unsettle, or create suspense",
                "humor_and_comedy": "Light-hearted, funny, and comedic content",
                "manga": "Japanese comic books and graphic novels",
                "memoir": "Personal accounts and autobiographical narratives",
                "music": "Books about musical history, theory, and musicians",
                "mystery": "Stories involving puzzles, crimes, or unexplained events to be solved",
                "nonfiction": "Factual writing on real subjects and events",
                "paranormal": "Stories involving supernatural or unexplained phenomena",
                "philosophy": "Works exploring fundamental questions about existence, knowledge, and ethics",
                "poetry": "Literary works in verse expressing emotions and ideas",
                "psychology": "Study of mind, behavior, and mental processes",
                "religion": "Spiritual and religious texts and teachings",
                "romance": "Stories focusing on romantic relationships and emotional connections",
                "science": "Educational works about scientific discoveries, theories, and research",
                "science_fiction": "Speculative fiction dealing with futuristic concepts and advanced technology",
                "self_help": "Personal development and improvement guides",
                "suspense": "Tension-filled stories with uncertain outcomes",
                "spirituality": "Exploration of spiritual beliefs and practices",
                "sports": "Athletic activities, sports history, and competition",
                "thriller": "Fast-paced stories with constant danger and excitement",
                "travel": "Travel guides, adventure stories, and cultural exploration",
                "young_adult": "Literature targeted at teenage and young adult readers",
            }

            genre_obj = {
                "id": genre_id,
                "name": genre_name,
                "book_count": book_count,
                "description": descriptions.get(genre_id, f"Literature in the {genre_name.lower()} category"),
            }
            genres.append(genre_obj)

        return genres

    def list(self, request, *args, **kwargs):
        """List all genres with filtering and search capabilities."""
        from rest_framework import status as http_status

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


# AIDEV-NOTE: Debug view to inspect request headers - remove after debugging auth issues
@api_view(["GET", "POST"])
@permission_classes([AllowAny])  # Allow without auth for debugging
def debug_headers(request):
    """
    Debug endpoint to see all request headers and auth info.
    Accessible at /api/debug/headers/
    """
    headers = {}
    for key, value in request.META.items():
        if key.startswith("HTTP_"):
            header_name = key[5:].replace("_", "-").title()
            headers[header_name] = value
        elif key in ["CONTENT_TYPE", "CONTENT_LENGTH"]:
            headers[key.replace("_", "-").title()] = value

    auth_info = {
        "user": str(request.user),
        "is_authenticated": request.user.is_authenticated,
        "auth_object": str(request.auth) if request.auth else None,
        "auth_type": type(request.auth).__name__ if request.auth else None,
    }

    return Response(
        {
            "method": request.method,
            "path": request.path,
            "headers": headers,
            "auth_info": auth_info,
            "remote_addr": request.META.get("REMOTE_ADDR"),
            "user_agent": request.META.get("HTTP_USER_AGENT"),
            "message": "This endpoint shows all headers and auth info for debugging",
        }
    )
