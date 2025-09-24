from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import
from mybooks.api import GroupList, UserDetails, UserList 

router = DefaultRouter()
router.register(r'books', BookViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path("api/users/", UserList.as_view()),
    path("api/users/<pk>/", UserDetails.as_view()),
    path("api/groups/", GroupList.as_view())
]