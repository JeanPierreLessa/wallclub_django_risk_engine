"""
URLs OAuth
"""
from django.urls import path
from . import views

urlpatterns = [
    path('token/', views.token, name='oauth_token'),
    path('health/', views.health, name='oauth_health'),
]
