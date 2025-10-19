FROM python:3.11-slim

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=America/Sao_Paulo

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar código
COPY . .

# Coletar arquivos estáticos
RUN python manage.py collectstatic --noinput || true

# Criar diretório de logs
RUN mkdir -p /app/logs

# Expor porta (apenas para container riskengine)
EXPOSE 8004

# Comando padrão (será sobrescrito pelo docker-compose.yml)
CMD ["gunicorn", "riskengine.wsgi:application", "--bind", "0.0.0.0:8004", "--workers", "3", "--timeout", "120"]
