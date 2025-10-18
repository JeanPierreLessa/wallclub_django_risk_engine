"""
Views OAuth para geração de tokens de acesso
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import connection
import secrets
import hashlib
import logging
from datetime import datetime, timedelta

logger = logging.getLogger('oauth')


@csrf_exempt
@require_http_methods(["POST"])
def token(request):
    """
    Endpoint OAuth 2.0 para geração de access tokens
    
    POST /oauth/token/
    
    Body (form-data):
        grant_type: client_credentials
        client_id: ID do cliente
        client_secret: Secret do cliente
    
    Response:
    {
        "access_token": "...",
        "token_type": "Bearer",
        "expires_in": 3600
    }
    """
    try:
        # Extrair credenciais (aceita form-data ou JSON)
        import json
        logger.info(f"OAuth token request - Content-Type: {request.content_type}")
        
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            grant_type = data.get('grant_type')
            client_id = data.get('client_id')
            client_secret = data.get('client_secret')
            logger.info(f"JSON request - client_id: {client_id}")
        else:
            grant_type = request.POST.get('grant_type')
            client_id = request.POST.get('client_id')
            client_secret = request.POST.get('client_secret')
            logger.info(f"Form request - client_id: {client_id}")
        
        # Validar grant_type
        if grant_type != 'client_credentials':
            return JsonResponse({
                'error': 'unsupported_grant_type',
                'error_description': 'Only client_credentials is supported'
            }, status=400)
        
        # Validar credenciais obrigatórias
        if not client_id or not client_secret:
            return JsonResponse({
                'error': 'invalid_request',
                'error_description': 'client_id and client_secret are required'
            }, status=400)
        
        # Buscar cliente no banco
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, client_id, client_secret, name, is_active, allowed_scopes
                FROM oauth_clients
                WHERE client_id = %s
            """, [client_id])
            
            row = cursor.fetchone()
            
            if not row:
                return JsonResponse({
                    'error': 'invalid_client',
                    'error_description': 'Client not found'
                }, status=401)
            
            db_id, db_client_id, db_client_secret, name, is_active, allowed_scopes = row
            
            # Verificar se está ativo
            if not is_active:
                return JsonResponse({
                    'error': 'invalid_client',
                    'error_description': 'Client is not active'
                }, status=401)
            
            # Verificar secret
            if client_secret != db_client_secret:
                return JsonResponse({
                    'error': 'invalid_client',
                    'error_description': 'Invalid client_secret'
                }, status=401)
        
        # Gerar token
        token_string = secrets.token_urlsafe(48)
        expires_in = 3600  # 1 hora
        
        # Salvar token no cache/banco (simplificado - apenas retorna)
        # Em produção, você pode querer salvar no Redis ou tabela
        
        return JsonResponse({
            'access_token': token_string,
            'token_type': 'Bearer',
            'expires_in': expires_in,
            'scope': allowed_scopes or 'read,write'
        })
        
    except Exception as e:
        logger.error(f"OAuth error: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': 'server_error',
            'error_description': str(e)
        }, status=500)


@require_http_methods(["GET"])
def health(request):
    """
    Health check do sistema OAuth
    
    GET /oauth/health/
    """
    return JsonResponse({
        'status': 'ok',
        'service': 'oauth',
        'timestamp': datetime.now().isoformat()
    })
