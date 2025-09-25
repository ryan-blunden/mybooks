from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

# Create router and register ViewSets
router = DefaultRouter()
router.register(r"books", views.UserBookViewSet, basename="userbook")
router.register(r"authors", views.AuthorViewSet, basename="author")
router.register(r"reviews", views.ReviewViewSet, basename="review")
router.register(r"browse", views.BookViewSet, basename="book")
router.register(r"genres", views.GenreViewSet, basename="genre")

# URL patterns
urlpatterns = [
    path("", include(router.urls)),
]
