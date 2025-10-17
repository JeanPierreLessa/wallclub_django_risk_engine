"""
API Decorators simplificados para Risk Engine
"""
from functools import wraps
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


def handle_api_errors(view_func):
    """
    Captura exceções e retorna resposta JSON padronizada
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Erro em {view_func.__name__}: {str(e)}", exc_info=True)
            return Response({
                'sucesso': False,
                'erro': str(e)
            }, status=500)
    return wrapper


def validate_required_params(required_params):
    """
    Valida se parâmetros obrigatórios estão presentes no request
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            missing = []
            for param in required_params:
                if param not in request.data:
                    missing.append(param)
            
            if missing:
                return Response({
                    'sucesso': False,
                    'erro': f'Parâmetros obrigatórios ausentes: {", ".join(missing)}'
                }, status=400)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
