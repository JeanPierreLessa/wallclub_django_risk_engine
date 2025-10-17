"""
ConfigManager simplificado para Risk Engine
Busca credenciais do AWS Secrets Manager
"""
import json
import os
import boto3
from typing import Any, Dict


class ConfigManager:
    """
    Gerenciador de configurações que usa AWS Secrets Manager
    """
    
    def __init__(self):
        self.is_production = self._detect_production_environment()
        self._secrets_client = None
        self._initialize_aws_clients()
    
    def _detect_production_environment(self) -> bool:
        """
        Detecta se está em ambiente de produção
        """
        environment = os.getenv('ENVIRONMENT', 'development').lower()
        return environment == 'production'
    
    def _get_secret_name(self) -> str:
        """
        Retorna o nome do secret baseado no ambiente
        """
        if self.is_production:
            return os.getenv('AWS_SECRET_NAME_PROD', 'wall/prod/db')
        else:
            return os.getenv('AWS_SECRET_NAME_DEV', 'wall/dev/db')
    
    def _initialize_aws_clients(self):
        """
        Inicializa clientes AWS
        """
        try:
            region = os.getenv('AWS_REGION', 'us-east-1')
            self._secrets_client = boto3.client('secretsmanager', region_name=region)
        except Exception as e:
            print(f"Erro ao inicializar AWS client: {e}")
            self._secrets_client = None
    
    def get_secret(self, secret_name: str, default: Any = None) -> Any:
        """
        Busca um secret do AWS Secrets Manager
        """
        try:
            if not self._secrets_client:
                return default
                
            response = self._secrets_client.get_secret_value(SecretId=secret_name)
            return response['SecretString']
            
        except Exception as e:
            print(f"Erro ao buscar secret {secret_name}: {e}")
            return default
    
    def get_database_config(self) -> Dict[str, Any]:
        """
        Obtém configurações do banco de dados do AWS Secret
        """
        try:
            secret_string = self.get_secret(self._get_secret_name())
            if not secret_string:
                return {}
                
            secrets = json.loads(secret_string)
            
            config = {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': secrets.get('DB_DATABASE_PYTHON'),  
                'USER': secrets.get('DB_USER_PYTHON'),
                'PASSWORD': secrets.get('DB_PASS_PYTHON'),
                'HOST': secrets.get('DB_HOST'),
                'PORT': '3306',  
                'OPTIONS': {
                    'charset': 'utf8mb4',
                    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                },
            }
            
            # Validar campos críticos
            critical_fields = ['USER', 'PASSWORD', 'HOST']
            missing_fields = [field for field in critical_fields if not config.get(field)]
            
            if missing_fields:
                print(f"Campos faltando no secret: {missing_fields}")
                return {}
            
            return config
            
        except Exception as e:
            print(f"Erro ao buscar config do banco: {e}")
            return {}


# Instância global
_config_manager_instance = None

def get_config_manager():
    """
    Retorna a instância do ConfigManager
    """
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()
    return _config_manager_instance
