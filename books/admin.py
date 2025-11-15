from django.contrib import admin

from .models import Author, Book, Review, UserBook


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "genre", "created_at")
    search_fields = ("title", "tagline", "author__name")
    list_filter = ("genre", "created_at")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("title",)
    list_select_related = ("author",)


@admin.register(UserBook)
class UserBookAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "reading_status", "date_added")
    search_fields = ("user__username", "book__title")
    list_filter = ("reading_status", "date_added")
    ordering = ("-date_added",)
    list_select_related = ("user", "book")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "rating", "created_at")
    search_fields = ("user__username", "book__title", "text")
    list_filter = ("rating", "created_at")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    list_select_related = ("user", "book")
