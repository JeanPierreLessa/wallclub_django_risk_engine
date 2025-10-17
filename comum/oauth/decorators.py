"""
Decorators OAuth simplificados para Risk Engine
"""
from functools import wraps


def require_oauth_token(view_func):
    """
    Decorator simplificado - em produção, validar token OAuth
    Por enquanto, permite acesso direto
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # TODO: Implementar validação de token OAuth real
        # Por enquanto, permite acesso direto
        return view_func(request, *args, **kwargs)
    return wrapper
