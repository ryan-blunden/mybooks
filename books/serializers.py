from django.utils import timezone
from rest_framework import serializers

from .models import Author, Book, Review, UserBook


class AuthorSerializer(serializers.ModelSerializer):
    """Serializer for Author model with nested book relationships.

    Provides comprehensive author information including biographical details
    and the total count of books they have authored.
    """

    books_count = serializers.SerializerMethodField(help_text="Total number of books authored by this person")

    class Meta:
        model = Author
        fields = ["id", "name", "image", "biography", "books_count", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {
            "name": {"help_text": "Author's full name (must be unique)"},
            "image": {"help_text": "Profile photo of the author", "allow_null": True},
            "biography": {
                "help_text": "Biographical information about the author",
                "allow_blank": True,
            },
            "id": {"help_text": "Unique identifier for the author"},
        }

    def get_books_count(self, obj) -> int:
        """Return the number of books by this author."""
        return obj.books.count()


class BookSerializer(serializers.ModelSerializer):
    """Serializer for Book model with comprehensive author information.

    Handles both reading book data with nested author details and creating
    new books with automatic author creation or lookup.
    """

    author = AuthorSerializer(read_only=True, help_text="Complete author information including biography and book count")
    author_name = serializers.CharField(
        write_only=True,
        help_text="Author name for creating/getting author. If author doesn't exist, they will be created automatically.",
    )

    class Meta:
        model = Book
        fields = ["id", "title", "tagline", "description", "image", "genre", "author", "author_name", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for the book"},
            "title": {"help_text": "The title of the book"},
            "tagline": {
                "help_text": "Brief description or tagline for the book",
                "allow_blank": True,
            },
            "description": {
                "help_text": "Detailed description of the book's plot and themes",
                "allow_blank": True,
            },
            "image": {"help_text": "Book cover image", "allow_null": True},
            "genre": {"help_text": "Book genre category"},
        }

    def create(self, validated_data):
        """Create book with get_or_create logic for author."""
        author_name = validated_data.pop("author_name")
        author, created = Author.objects.get_or_create(name=author_name, defaults={"name": author_name})
        validated_data["author"] = author
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update book, handling author changes if needed."""
        if "author_name" in validated_data:
            author_name = validated_data.pop("author_name")
            author, created = Author.objects.get_or_create(name=author_name, defaults={"name": author_name})
            validated_data["author"] = author
        return super().update(instance, validated_data)


class UserBookSerializer(serializers.ModelSerializer):
    """Serializer for UserBook model with comprehensive book and reading status management.

    Supports both adding existing books to collection via book_id or creating
    new books directly with title, author_name, and genre fields.
    """

    book = BookSerializer(read_only=True, help_text="Complete book information including author details")
    book_id = serializers.IntegerField(write_only=True, required=False, help_text="ID of existing book to add to collection")

    # Support creating books directly within UserBook
    title = serializers.CharField(write_only=True, required=False, help_text="Title for new book (used when creating book inline)")
    author_name = serializers.CharField(write_only=True, required=False, help_text="Author name for new book (used when creating book inline)")
    genre = serializers.ChoiceField(
        choices=Book.GENRE_CHOICES, write_only=True, required=False, help_text="Genre for new book (used when creating book inline)"
    )
    tagline = serializers.CharField(write_only=True, required=False, allow_blank=True, help_text="Brief tagline for new book (optional)")
    description = serializers.CharField(write_only=True, required=False, allow_blank=True, help_text="Detailed description for new book (optional)")

    class Meta:
        model = UserBook
        fields = [
            "id",
            "book",
            "book_id",
            "reading_status",
            "date_added",
            "date_started",
            "date_finished",
            # Book creation fields
            "title",
            "author_name",
            "genre",
            "tagline",
            "description",
        ]
        read_only_fields = ["date_added", "date_started", "date_finished"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for this user-book relationship"},
            "reading_status": {"help_text": "Current reading status for this book"},
            "date_added": {"help_text": "When this book was added to the user's collection", "format": "date-time"},
            "date_started": {
                "help_text": "When the user started reading this book (auto-set when status changes to 'reading')",
                "format": "date-time",
                "allow_null": True,
            },
            "date_finished": {
                "help_text": "When the user finished reading this book (auto-set when status changes to 'finished')",
                "format": "date-time",
                "allow_null": True,
            },
            "book_id": {"help_text": "ID of existing book to add to collection"},
            "title": {"help_text": "Title for new book (used when creating book inline)"},
            "author_name": {"help_text": "Author name for new book (used when creating book inline)"},
            "genre": {"help_text": "Genre for new book (used when creating book inline)"},
            "tagline": {"help_text": "Brief tagline for new book (optional)"},
            "description": {"help_text": "Detailed description for new book (optional)"},
        }

    def validate(self, data):
        """Validate that either book_id or book creation fields are provided on create, not required on update."""
        request = self.context.get("request")
        method = getattr(request, "method", None)
        has_book_id = "book_id" in data
        has_book_fields = any(field in data for field in ["title", "author_name", "genre"])

        if method == "POST":
            if not has_book_id and not has_book_fields:
                raise serializers.ValidationError("Either provide book_id or book creation fields (title, author_name, genre)")
            if has_book_id and has_book_fields:
                raise serializers.ValidationError("Provide either book_id or book creation fields, not both")
        # For PUT/PATCH, don't require book_id or book creation fields
        return data

    def create(self, validated_data):
        """Create UserBook, handling book creation if needed."""
        user = self.context["request"].user

        # Extract book creation fields
        book_fields = {}
        for field in ["title", "author_name", "genre", "tagline", "description"]:
            if field in validated_data:
                book_fields[field] = validated_data.pop(field)

        if book_fields:
            # Create book using BookSerializer
            book_serializer = BookSerializer(data=book_fields)
            book_serializer.is_valid(raise_exception=True)
            book = book_serializer.save()
            validated_data["book"] = book
        else:
            # Use existing book
            book_id = validated_data.pop("book_id")
            try:
                book = Book.objects.get(id=book_id)
                validated_data["book"] = book
            except Book.DoesNotExist:
                raise serializers.ValidationError({"book_id": "Book not found"})

        # Check for duplicate user-book combination
        if UserBook.objects.filter(user=user, book=validated_data["book"]).exists():
            raise serializers.ValidationError("This book is already in your collection")

        validated_data["user"] = user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update UserBook with automatic date handling for status changes."""
        old_status = instance.reading_status
        new_status = validated_data.get("reading_status", old_status)

        # Auto-set date_started when changing to 'reading'
        if old_status != "reading" and new_status == "reading":
            validated_data["date_started"] = timezone.now()

        # Auto-set date_finished when changing to 'finished'
        if old_status != "finished" and new_status == "finished":
            validated_data["date_finished"] = timezone.now()

        # Clear date_finished if changing away from 'finished'
        if old_status == "finished" and new_status != "finished":
            validated_data["date_finished"] = None

        return super().update(instance, validated_data)


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for Review model with comprehensive validation and user-book relationships.

    Ensures users can only review books once and validates rating scores.
    """

    book = BookSerializer(read_only=True, help_text="Complete book information for the reviewed book")
    book_id = serializers.IntegerField(write_only=True, help_text="ID of the book being reviewed")
    user = serializers.StringRelatedField(read_only=True, help_text="Username of the reviewer")

    class Meta:
        model = Review
        fields = ["id", "book", "book_id", "user", "rating", "text", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {
            "id": {"help_text": "Unique identifier for this review"},
            "rating": {"help_text": "Star rating from 1 to 5 stars", "min_value": 1, "max_value": 5},
            "text": {
                "help_text": "Written review content (optional)",
                "allow_blank": True,
            },
            "created_at": {"help_text": "When this review was created", "format": "date-time"},
            "updated_at": {"help_text": "When this review was last updated", "format": "date-time"},
        }

    def validate_rating(self, value):
        """Validate rating is between 1 and 5."""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value

    def validate_book_id(self, value):
        """Validate that book exists."""
        try:
            Book.objects.get(id=value)
        except Book.DoesNotExist:
            raise serializers.ValidationError("Book not found")
        return value

    def create(self, validated_data):
        """Create review with user from request and duplicate checking."""
        user = self.context["request"].user
        book_id = validated_data.pop("book_id")
        book = Book.objects.get(id=book_id)

        # Check for duplicate user-book review combination
        if Review.objects.filter(user=user, book=book).exists():
            raise serializers.ValidationError("You have already reviewed this book")

        validated_data["user"] = user
        validated_data["book"] = book
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update review, preventing book_id changes."""
        if "book_id" in validated_data:
            validated_data.pop("book_id")  # Don't allow changing the book
        return super().update(instance, validated_data)


# Additional serializers for detailed views
class AuthorDetailSerializer(AuthorSerializer):
    """Detailed serializer for Author with list of books."""

    books = BookSerializer(many=True, read_only=True)

    class Meta(AuthorSerializer.Meta):
        fields = AuthorSerializer.Meta.fields + ["books"]


class UserBookDetailSerializer(UserBookSerializer):
    """Detailed serializer for UserBook including review if exists."""

    review = serializers.SerializerMethodField()

    class Meta(UserBookSerializer.Meta):
        fields = UserBookSerializer.Meta.fields + ["review"]

    def get_review(self, obj) -> dict | None:
        """Get user's review for this book if it exists."""
        try:
            review = Review.objects.get(user=obj.user, book=obj.book)
            return ReviewSerializer(review, context=self.context).data
        except Review.DoesNotExist:
            return None


class GenreSerializer(serializers.Serializer):
    """Serializer for Genre information with book counts and metadata.

    Provides comprehensive information about book genres including the number
    of books available in each genre category.
    """

    id = serializers.CharField(help_text="Unique genre identifier (slug format)")
    name = serializers.CharField(help_text="Human-readable genre name")
    book_count = serializers.IntegerField(help_text="Total number of books in this genre")
    description = serializers.CharField(help_text="Optional description of the genre", allow_blank=True)

    class Meta:
        fields = ["id", "name", "book_count", "description"]


class DebugAuthInfoSerializer(serializers.Serializer):
    """Serializer describing authentication metadata captured by debug endpoint."""

    user = serializers.CharField(help_text="String representation of the authenticated user")
    is_authenticated = serializers.BooleanField(help_text="Whether the request user is authenticated")
    auth_object = serializers.CharField(
        help_text="String representation of the auth token or object",
        allow_null=True,
        required=False,
    )
    auth_type = serializers.CharField(
        help_text="Class name of the auth object, if any",
        allow_null=True,
        required=False,
    )


class DebugHeadersResponseSerializer(serializers.Serializer):
    """Serializer for debug headers endpoint response."""

    method = serializers.CharField(help_text="HTTP method used for the request (e.g., GET)")
    path = serializers.CharField(help_text="Full request path")
    headers = serializers.DictField(
        child=serializers.CharField(),
        help_text="Request headers keyed by header name",
    )
    auth_info = DebugAuthInfoSerializer(help_text="Authentication metadata for the request")
    remote_addr = serializers.CharField(
        help_text="IP address of the client making the request",
        allow_null=True,
        required=False,
    )
    user_agent = serializers.CharField(
        help_text="User agent string provided by the client",
        allow_null=True,
        required=False,
    )
    message = serializers.CharField(help_text="Human-readable explanation of the endpoint purpose")
