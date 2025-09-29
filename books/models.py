from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Author(models.Model):
    """Represents book authors with optional biographical information."""

    name = models.CharField(max_length=255, unique=True, help_text="Author's full name")
    image = models.ImageField(upload_to="authors/", blank=True, null=True, help_text="Author photo")
    biography = models.TextField(blank=True, help_text="Author biographical information")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Book(models.Model):
    """Represents books that can be added to user collections."""

    # Genre choices
    GENRE_CHOICES = [
        ("art", "Art"),
        ("biography", "Biography"),
        ("business", "Business"),
        ("chick_lit", "Chick Lit"),
        ("childrens", "Children's"),
        ("christian", "Christian"),
        ("classics", "Classics"),
        ("comics", "Comics"),
        ("contemporary", "Contemporary"),
        ("cookbooks", "Cookbooks"),
        ("crime", "Crime"),
        ("ebooks", "Ebooks"),
        ("fantasy", "Fantasy"),
        ("fiction", "Fiction"),
        ("gay_and_lesbian", "Gay and Lesbian"),
        ("graphic_novels", "Graphic Novels"),
        ("historical_fiction", "Historical Fiction"),
        ("history", "History"),
        ("horror", "Horror"),
        ("humor_and_comedy", "Humor and Comedy"),
        ("manga", "Manga"),
        ("memoir", "Memoir"),
        ("music", "Music"),
        ("mystery", "Mystery"),
        ("nonfiction", "Nonfiction"),
        ("paranormal", "Paranormal"),
        ("philosophy", "Philosophy"),
        ("poetry", "Poetry"),
        ("psychology", "Psychology"),
        ("religion", "Religion"),
        ("romance", "Romance"),
        ("science", "Science"),
        ("science_fiction", "Science Fiction"),
        ("self_help", "Self Help"),
        ("suspense", "Suspense"),
        ("spirituality", "Spirituality"),
        ("sports", "Sports"),
        ("thriller", "Thriller"),
        ("travel", "Travel"),
        ("young_adult", "Young Adult"),
    ]

    title = models.CharField(max_length=255, help_text="Book title")
    tagline = models.CharField(max_length=500, blank=True, help_text="Brief book description")
    description = models.TextField(blank=True, help_text="Detailed book description")
    image = models.ImageField(upload_to="books/", blank=True, null=True, help_text="Book cover image")
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    genre = models.CharField(max_length=50, choices=GENRE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        unique_together = ["title", "author"]

    def __str__(self):
        return f"{self.title} by {self.author.name}"


class UserBook(models.Model):
    """Junction table linking users to books with reading status and tracking information."""

    # Reading Status Choices
    READING_STATUS_CHOICES = [
        ("want_to_read", "Want to Read"),
        ("reading", "Reading"),
        ("finished", "Finished"),
        ("dropped", "Dropped"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_books")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="user_books")
    reading_status = models.CharField(max_length=20, choices=READING_STATUS_CHOICES, default="want_to_read")
    date_added = models.DateTimeField(auto_now_add=True)
    date_started = models.DateTimeField(blank=True, null=True)
    date_finished = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-date_added"]
        unique_together = ["user", "book"]

    def __str__(self):
        return f"{self.user.username} - {self.book.title} ({self.reading_status})"


class Review(models.Model):
    """User reviews and ratings for books they've read."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reviews")
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], help_text="Star rating from 1-5")
    text = models.TextField(blank=True, help_text="Review text content")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ["user", "book"]

    def __str__(self):
        return f"{self.user.username} - {self.book.title} ({self.rating}/5)"
