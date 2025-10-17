"""
OAuth Services simplificados para Risk Engine
"""
import hashlib


class OAuthService:
    """
    Service simplificado para extração de dados do request
    """
    
    @staticmethod
    def extract_device_fingerprint(request):
        """
        Extrai fingerprint do dispositivo baseado em User-Agent e IP
        """
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        ip_address = request.META.get('REMOTE_ADDR', '')
        
        # Criar hash do UA + IP como fingerprint
        fingerprint_string = f"{user_agent}|{ip_address}"
        fingerprint = hashlib.md5(fingerprint_string.encode()).hexdigest()
        
        return fingerprint
