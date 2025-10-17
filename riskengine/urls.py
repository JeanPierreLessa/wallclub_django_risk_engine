"""
URLs do WallClub Risk Engine
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/antifraude/', include('antifraude.urls')),
    path('oauth/', include('comum.oauth.urls')),
]
