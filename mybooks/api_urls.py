from django.urls import path, include
from rest_framework.routers import DefaultRouter
from mybooks.api import GroupList, UserDetails, UserList 

# TODO: add BookViewSet and import it here

# router = DefaultRouter()
# router.register(r'books', BookViewSet)

# urlpatterns = [
#     path('', include(router.urls)),
# ]