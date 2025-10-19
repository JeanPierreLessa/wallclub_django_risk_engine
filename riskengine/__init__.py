"""
Risk Engine Package
Inicialização do Celery para autodiscovery de tasks
"""
from .celery import app as celery_app

__all__ = ('celery_app',)
