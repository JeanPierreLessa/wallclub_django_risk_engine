"""
Settings para WallClub Risk Engine
Sistema Antifraude - Porta 8004
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-riskengine-change-in-production')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'corsheaders',
    
    # Local apps
    'antifraude',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'riskengine.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'riskengine.wsgi.application'

# Database (MySQL compartilhado com app principal via AWS Secrets)
# OBRIGATÓRIO: Credenciais devem vir do AWS Secrets Manager
# Se falhar, aplicação não deve iniciar (sem fallback por segurança)
from wallclub_core.utilitarios.config_manager import get_config_manager

config_manager = get_config_manager()
db_config = config_manager.get_database_config()

if not db_config:
    raise RuntimeError(
        "ERRO CRÍTICO: Não foi possível obter configurações do banco de dados do AWS Secrets Manager. "
        "Verifique as credenciais AWS e a conexão com o Secrets Manager."
    )

DATABASES = {'default': db_config}

# Cache (Redis compartilhado)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', '6379')}/2",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = False  # Timezone naive (compatível com MySQL)

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS (permitir comunicação com app principal)
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:8003').split(',')
CORS_ALLOW_CREDENTIALS = True

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
}

# Configurações customizadas
CALLBACK_URL_PRINCIPAL = os.environ.get('CALLBACK_URL_PRINCIPAL', 'http://wallclub-prod-release300:8000')
NOTIFICACAO_EMAIL = os.environ.get('NOTIFICACAO_EMAIL', 'admin@wallclub.com.br')
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')

# MaxMind minFraud (Semana 9) - Lê do AWS Secrets Manager
_maxmind_config = config_manager.get_maxmind_config()
MAXMIND_ACCOUNT_ID = _maxmind_config.get('account_id')
MAXMIND_LICENSE_KEY = _maxmind_config.get('license_key')

# 3D Secure 2.0 (Semana 13)
THREEDS_ENABLED = os.environ.get('THREEDS_ENABLED', 'False') == 'True'
THREEDS_GATEWAY_URL = os.environ.get('THREEDS_GATEWAY_URL', None)
THREEDS_MERCHANT_ID = os.environ.get('THREEDS_MERCHANT_ID', None)
THREEDS_MERCHANT_KEY = os.environ.get('THREEDS_MERCHANT_KEY', None)
THREEDS_TIMEOUT = int(os.environ.get('THREEDS_TIMEOUT', '30'))

# Celery Configuration (Containers separados)
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', '6379')}/0")
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', f"redis://{os.environ.get('REDIS_HOST', 'redis')}:{os.environ.get('REDIS_PORT', '6379')}/0")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/Sao_Paulo'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutos
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000  # Restart worker após 1000 tasks
