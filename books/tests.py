"""
Comprehensive tests for Books API covering essential CRUD and search functionality.

Tests all four main endpoints:
- /api/books/ (UserBookViewSet) - User's personal book collection
- /api/authors/ (AuthorViewSet) - Author discovery and information
- /api/reviews/ (ReviewViewSet) - User reviews and ratings
- /api/browse/ (BookViewSet) - Browse all books in system

AIDEV-NOTE: These tests focus on essential functionality only, following the golden rule
of not modifying test files without permission. Tests cover CRUD operations, search,
filtering, and business logic validation.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Author, Book, Review, UserBook


class BooksAPIBaseTestCase(APITestCase):
    """Base test case with common setup for all Books API tests."""

    def setUp(self):
        """Set up test data and authentication."""
        # Create test users
        self.user1 = User.objects.create_user(username="testuser1", email="test1@example.com", password="testpass123")
        self.user2 = User.objects.create_user(username="testuser2", email="test2@example.com", password="testpass123")

        # Create tokens for authentication
        self.token1 = Token.objects.create(user=self.user1)
        self.token2 = Token.objects.create(user=self.user2)

        # Create test authors
        self.tolkien = Author.objects.create(
            name="J.R.R. Tolkien",
            biography="English writer, poet, philologist, and academic, best known as the author of The Hobbit and The Lord of the Rings.",
        )
        self.rowling = Author.objects.create(name="J.K. Rowling", biography="British author, best known for the Harry Potter fantasy series.")

        # Create test books
        self.hobbit = Book.objects.create(
            title="The Hobbit",
            author=self.tolkien,
            genre="fantasy",
            description="A reluctant Hobbit, Bilbo Baggins, sets out to the Lonely Mountain.",
        )
        self.lotr = Book.objects.create(
            title="The Lord of the Rings",
            author=self.tolkien,
            genre="fantasy",
            description="Epic fantasy adventure following Frodo's quest to destroy the One Ring.",
        )
        self.hp1 = Book.objects.create(
            title="Harry Potter and the Philosopher's Stone",
            author=self.rowling,
            genre="fantasy",
            description="Young wizard Harry Potter discovers his magical heritage.",
        )

    def authenticate_user1(self):
        """Authenticate as user1."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token1.key}")

    def authenticate_user2(self):
        """Authenticate as user2."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token2.key}")


class AuthorAPITestCase(BooksAPIBaseTestCase):
    """Test Author API endpoints (/api/authors/)."""

    def test_list_authors_authenticated(self):
        """Test listing all authors with authentication."""
        self.authenticate_user1()
        url = reverse("author-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

        # Check first author data
        author_data = response.data["results"][0]
        self.assertIn("id", author_data)
        self.assertIn("name", author_data)
        self.assertIn("biography", author_data)
        self.assertIn("books_count", author_data)

    def test_list_authors_unauthenticated(self):
        """Test that unauthenticated requests are rejected."""
        url = reverse("author-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_author_details(self):
        """Test retrieving detailed author information."""
        self.authenticate_user1()
        url = reverse("author-detail", kwargs={"pk": self.tolkien.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "J.R.R. Tolkien")
        self.assertEqual(response.data["books_count"], 2)  # Hobbit + LOTR

    def test_search_authors_by_name(self):
        """Test searching authors by name."""
        self.authenticate_user1()
        url = reverse("author-list")
        response = self.client.get(url, {"search": "Tolkien"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "J.R.R. Tolkien")

    def test_search_authors_by_biography(self):
        """Test searching authors by biography content."""
        self.authenticate_user1()
        url = reverse("author-list")
        response = self.client.get(url, {"search": "Harry Potter"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "J.K. Rowling")


class UserBookAPITestCase(BooksAPIBaseTestCase):
    """Test UserBook API endpoints (/api/books/) - User's personal collection."""

    def test_empty_collection_initially(self):
        """Test that user's collection is empty initially."""
        self.authenticate_user1()
        url = reverse("userbook-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_add_existing_book_to_collection(self):
        """Test adding an existing book to user's collection."""
        self.authenticate_user1()
        url = reverse("userbook-list")

        data = {"book_id": self.hobbit.pk, "reading_status": "want_to_read"}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["reading_status"], "want_to_read")
        self.assertEqual(response.data["book"]["title"], "The Hobbit")

        # Verify it appears in collection
        response = self.client.get(url)
        self.assertEqual(len(response.data["results"]), 1)

    def test_add_new_book_inline_to_collection(self):
        """Test creating a new book directly when adding to collection."""
        self.authenticate_user1()
        url = reverse("userbook-list")

        data = {
            "title": "The Fellowship of the Ring",
            "author_name": "J.R.R. Tolkien",
            "genre": "fantasy",
            "reading_status": "reading",
            "description": "First volume of The Lord of the Rings",
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["reading_status"], "reading")
        self.assertEqual(response.data["book"]["title"], "The Fellowship of the Ring")
        self.assertEqual(response.data["book"]["author"]["name"], "J.R.R. Tolkien")

    def test_update_reading_status(self):
        """Test updating reading status of book in collection."""
        # Add book to collection first
        self.authenticate_user1()
        userbook = UserBook.objects.create(user=self.user1, book=self.hobbit, reading_status="want_to_read")

        url = reverse("userbook-detail", kwargs={"pk": userbook.pk})
        data = {"reading_status": "finished", "book_id": self.hobbit.id}
        response = self.client.put(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["reading_status"], "finished")

    def test_remove_book_from_collection(self):
        """Test removing book from user's collection."""
        # Add book to collection first
        self.authenticate_user1()
        userbook = UserBook.objects.create(user=self.user1, book=self.hobbit, reading_status="want_to_read")

        url = reverse("userbook-detail", kwargs={"pk": userbook.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify it's removed from collection
        list_url = reverse("userbook-list")
        response = self.client.get(list_url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_filter_by_reading_status(self):
        """Test filtering user's books by reading status."""
        self.authenticate_user1()

        # Add books with different statuses
        UserBook.objects.create(user=self.user1, book=self.hobbit, reading_status="want_to_read")
        UserBook.objects.create(user=self.user1, book=self.lotr, reading_status="reading")
        UserBook.objects.create(user=self.user1, book=self.hp1, reading_status="finished")

        url = reverse("userbook-list")

        # Test filtering by status
        response = self.client.get(url, {"reading_status": "reading"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["book"]["title"], "The Lord of the Rings")

    def test_search_user_books(self):
        """Test searching within user's book collection."""
        self.authenticate_user1()

        # Add books to collection
        UserBook.objects.create(user=self.user1, book=self.hobbit, reading_status="finished")
        UserBook.objects.create(user=self.user1, book=self.hp1, reading_status="want_to_read")

        url = reverse("userbook-list")
        response = self.client.get(url, {"search": "Hobbit"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["book"]["title"], "The Hobbit")

    def test_user_isolation(self):
        """Test that users only see their own books."""
        # Add book to user1's collection
        self.authenticate_user1()
        UserBook.objects.create(user=self.user1, book=self.hobbit, reading_status="reading")

        # User2 should not see user1's books
        self.authenticate_user2()
        url = reverse("userbook-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)


class ReviewAPITestCase(BooksAPIBaseTestCase):
    """Test Review API endpoints (/api/reviews/)."""

    def test_create_review(self):
        """Test creating a review for a book."""
        self.authenticate_user1()
        url = reverse("review-list")

        data = {"book_id": self.hobbit.pk, "rating": 5, "text": "Absolutely fantastic book! A timeless classic."}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["rating"], 5)
        self.assertEqual(response.data["text"], "Absolutely fantastic book! A timeless classic.")
        self.assertEqual(response.data["book"]["title"], "The Hobbit")

    def test_create_review_with_invalid_rating(self):
        """Test that invalid ratings (outside 1-5) are rejected."""
        self.authenticate_user1()
        url = reverse("review-list")

        # Test rating too high
        data = {"book_id": self.hobbit.pk, "rating": 6, "text": "Great book"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test rating too low
        data = {"book_id": self.hobbit.pk, "rating": 0, "text": "Great book"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_review(self):
        """Test updating a review."""
        self.authenticate_user1()

        # Create review first
        review = Review.objects.create(user=self.user1, book=self.hobbit, rating=4, text="Good book")

        url = reverse("review-detail", kwargs={"pk": review.pk})
        data = {"rating": 5, "text": "Actually, this is an amazing book!", "book_id": self.hobbit.id}
        response = self.client.put(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rating"], 5)
        self.assertEqual(response.data["text"], "Actually, this is an amazing book!")

    def test_delete_review(self):
        """Test deleting a review."""
        self.authenticate_user1()

        # Create review first
        review = Review.objects.create(user=self.user1, book=self.hobbit, rating=4, text="Good book")

        url = reverse("review-detail", kwargs={"pk": review.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify review is deleted
        self.assertFalse(Review.objects.filter(pk=review.pk).exists())

    def test_list_user_reviews(self):
        """Test listing all reviews by authenticated user."""
        self.authenticate_user1()

        # Create multiple reviews
        Review.objects.create(user=self.user1, book=self.hobbit, rating=5, text="Love it!")
        Review.objects.create(user=self.user1, book=self.lotr, rating=4, text="Great epic")

        url = reverse("review-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_review_user_isolation(self):
        """Test that users only see their own reviews."""
        # Create review for user1
        Review.objects.create(user=self.user1, book=self.hobbit, rating=5, text="Amazing!")

        # User2 should not see user1's reviews
        self.authenticate_user2()
        url = reverse("review-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_duplicate_review_prevention(self):
        """Test that users cannot create multiple reviews for the same book."""
        self.authenticate_user1()

        # Create first review
        Review.objects.create(user=self.user1, book=self.hobbit, rating=5, text="Great!")

        # Try to create second review for same book
        url = reverse("review-list")
        data = {"book_id": self.hobbit.pk, "rating": 4, "text": "Different opinion"}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class BookBrowseAPITestCase(BooksAPIBaseTestCase):
    """Test Book Browse API endpoints (/api/browse/) - Browse all books in system."""

    def test_browse_all_books(self):
        """Test browsing all books in the system."""
        self.authenticate_user1()
        url = reverse("book-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)  # hobbit, lotr, hp1

    def test_browse_book_details(self):
        """Test retrieving detailed information about a specific book."""
        self.authenticate_user1()
        url = reverse("book-detail", kwargs={"pk": self.hobbit.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "The Hobbit")
        self.assertEqual(response.data["author"]["name"], "J.R.R. Tolkien")
        self.assertEqual(response.data["genre"], "fantasy")

    def test_filter_books_by_genre(self):
        """Test filtering books by genre."""
        # Create book with different genre
        Book.objects.create(
            title="A Brief History of Time",
            author=Author.objects.create(name="Stephen Hawking"),
            genre="science",
            description="Popular science book about cosmology",
        )

        self.authenticate_user1()
        url = reverse("book-list")

        # Filter by fantasy
        response = self.client.get(url, {"genre": "fantasy"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)  # Original test books are fantasy

        # Filter by science
        response = self.client.get(url, {"genre": "science"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "A Brief History of Time")

    def test_search_books_by_title(self):
        """Test searching books by title."""
        self.authenticate_user1()
        url = reverse("book-list")
        response = self.client.get(url, {"search": "Hobbit"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "The Hobbit")

    def test_search_books_by_author(self):
        """Test searching books by author name."""
        self.authenticate_user1()
        url = reverse("book-list")
        response = self.client.get(url, {"search": "Tolkien"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)  # Hobbit + LOTR

    def test_browse_books_unauthenticated(self):
        """Test that unauthenticated users cannot browse books."""
        url = reverse("book-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ModelValidationTestCase(TestCase):
    """Test model-level validation and business logic."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.author = Author.objects.create(name="Test Author")
        self.book = Book.objects.create(title="Test Book", author=self.author, genre="fiction")

    def test_unique_author_names(self):
        """Test that author names must be unique."""
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Author.objects.create(name="Test Author")  # Same name as setUp

    def test_unique_book_title_author_combination(self):
        """Test that book title + author combination must be unique."""
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Book.objects.create(title="Test Book", author=self.author, genre="mystery")  # Same title + author as setUp

    def test_unique_user_book_combination(self):
        """Test that user + book combination must be unique in UserBook."""
        UserBook.objects.create(user=self.user, book=self.book, reading_status="want_to_read")

        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            UserBook.objects.create(user=self.user, book=self.book, reading_status="reading")

    def test_unique_user_review_combination(self):
        """Test that user + book combination must be unique in Review."""
        Review.objects.create(user=self.user, book=self.book, rating=5, text="Great!")

        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Review.objects.create(user=self.user, book=self.book, rating=4, text="Different review")
