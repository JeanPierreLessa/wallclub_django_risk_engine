"""
Configuração Celery para Risk Engine
Sistema de Atividades Suspeitas - Semana 23
"""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'riskengine.settings')

app = Celery('riskengine')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


# Configuração de tarefas periódicas
app.conf.beat_schedule = {
    'detectar-atividades-suspeitas': {
        'task': 'antifraude.tasks.detectar_atividades_suspeitas',
        'schedule': 300.0,  # A cada 5 minutos
        'options': {'expires': 240}
    },
    'bloquear-automatico-critico': {
        'task': 'antifraude.tasks.bloquear_automatico_critico',
        'schedule': 600.0,  # A cada 10 minutos
        'options': {'expires': 540}
    },
}

app.conf.timezone = 'America/Sao_Paulo'
