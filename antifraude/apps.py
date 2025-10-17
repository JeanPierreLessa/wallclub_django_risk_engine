"""
Configuração do app Antifraude
"""
from django.apps import AppConfig


class Antifraude(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'antifraude'
    verbose_name = 'Sistema Antifraude'
