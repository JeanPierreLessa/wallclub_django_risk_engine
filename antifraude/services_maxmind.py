"""
Serviço de Integração com MaxMind minFraud
Fase 2 - Semana 9: Score externo de risco
"""
from decimal import Decimal
from datetime import datetime, timedelta
import requests
import json
from typing import Dict, Optional, Any
from django.core.cache import cache
from django.conf import settings


class MaxMindService:
    """
    Integração com MaxMind minFraud para análise de risco
    Documentação: https://dev.maxmind.com/minfraud
    """
    
    # Configurações
    API_URL = "https://minfraud.maxmind.com/minfraud/v2.0/score"
    CACHE_TIMEOUT = 3600  # 1 hora em segundos
    SCORE_NEUTRO = 50  # Score padrão quando API falha
    
    @staticmethod
    def _get_cache_key(cpf: str, valor: Decimal, ip: str = None) -> str:
        """
        Gera chave de cache única para consulta
        
        Args:
            cpf: CPF do cliente
            valor: Valor da transação
            ip: IP do cliente (opcional)
        
        Returns:
            Chave de cache
        """
        # CPF + valor arredondado + IP (se disponível)
        valor_int = int(valor)
        if ip:
            return f"maxmind:{cpf}:{valor_int}:{ip}"
        return f"maxmind:{cpf}:{valor_int}"
    
    @staticmethod
    def _preparar_payload(transacao_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepara payload para API MaxMind conforme formato exigido
        
        Args:
            transacao_data: Dados da transação
        
        Returns:
            Payload formatado para MaxMind
        """
        payload = {
            "device": {},
            "event": {
                "transaction_id": transacao_data.get('transacao_id'),
                "shop_id": str(transacao_data.get('loja_id', '')),
                "time": datetime.now().isoformat(),
                "type": "purchase"
            },
            "account": {
                "user_id": str(transacao_data.get('cliente_id', ''))
            },
            "billing": {
                "first_name": transacao_data.get('cliente_nome', '').split()[0] if transacao_data.get('cliente_nome') else '',
                "last_name": ' '.join(transacao_data.get('cliente_nome', '').split()[1:]) if transacao_data.get('cliente_nome') else ''
            },
            "order": {
                "amount": float(transacao_data.get('valor', 0)),
                "currency": "BRL"
            }
        }
        
        # Device info (se disponível)
        if transacao_data.get('ip_address'):
            payload['device']['ip_address'] = transacao_data['ip_address']
        
        if transacao_data.get('user_agent'):
            payload['device']['user_agent'] = transacao_data['user_agent']
        
        if transacao_data.get('device_fingerprint'):
            payload['device']['session_id'] = transacao_data['device_fingerprint']
        
        # Payment info
        if transacao_data.get('bin_cartao'):
            payload['payment'] = {
                "processor": "pinbank",
                "iin": transacao_data['bin_cartao']
            }
        
        return payload
    
    @staticmethod
    def consultar_score(transacao_data: Dict[str, Any], usar_cache: bool = True) -> Dict[str, Any]:
        """
        Consulta score de risco na API MaxMind
        
        Args:
            transacao_data: Dados da transação
            usar_cache: Se deve usar cache Redis (padrão: True)
        
        Returns:
            Dict com score e detalhes:
            {
                'score': 65,
                'risk_score': 0.65,
                'fonte': 'maxmind' | 'cache' | 'fallback',
                'detalhes': {...},
                'tempo_consulta_ms': 250
            }
        """
        cpf = transacao_data.get('cpf')
        valor = transacao_data.get('valor')
        ip = transacao_data.get('ip_address')
        
        # Verificar cache primeiro
        if usar_cache:
            cache_key = MaxMindService._get_cache_key(cpf, valor, ip)
            cached_score = cache.get(cache_key)
            
            if cached_score is not None:
                return {
                    'score': cached_score,
                    'risk_score': cached_score / 100,
                    'fonte': 'cache',
                    'detalhes': {'cached': True},
                    'tempo_consulta_ms': 0
                }
        
        # Verificar se credenciais estão configuradas
        account_id = getattr(settings, 'MAXMIND_ACCOUNT_ID', None)
        license_key = getattr(settings, 'MAXMIND_LICENSE_KEY', None)
        
        if not account_id or not license_key:
            # Fallback: retorna score neutro
            return {
                'score': MaxMindService.SCORE_NEUTRO,
                'risk_score': MaxMindService.SCORE_NEUTRO / 100,
                'fonte': 'fallback',
                'detalhes': {'motivo': 'Credenciais MaxMind não configuradas'},
                'tempo_consulta_ms': 0
            }
        
        # Preparar requisição
        payload = MaxMindService._preparar_payload(transacao_data)
        auth = (account_id, license_key)
        
        inicio = datetime.now()
        
        try:
            # Consultar API MaxMind
            response = requests.post(
                MaxMindService.API_URL,
                auth=auth,
                json=payload,
                timeout=3  # 3 segundos de timeout
            )
            
            tempo_ms = int((datetime.now() - inicio).total_seconds() * 1000)
            
            if response.status_code == 200:
                data = response.json()
                
                # MaxMind retorna risk_score de 0.01 a 99.99
                risk_score = data.get('risk_score', 50.0)
                score = int(risk_score)
                
                # Cachear resultado (1 hora)
                if usar_cache:
                    cache_key = MaxMindService._get_cache_key(cpf, valor, ip)
                    cache.set(cache_key, score, MaxMindService.CACHE_TIMEOUT)
                
                return {
                    'score': score,
                    'risk_score': risk_score / 100,
                    'fonte': 'maxmind',
                    'detalhes': {
                        'ip_risk': data.get('ip_address', {}).get('risk', None),
                        'warnings': data.get('warnings', []),
                        'id': data.get('id')
                    },
                    'tempo_consulta_ms': tempo_ms
                }
            
            else:
                # Erro na API: fallback
                return {
                    'score': MaxMindService.SCORE_NEUTRO,
                    'risk_score': MaxMindService.SCORE_NEUTRO / 100,
                    'fonte': 'fallback',
                    'detalhes': {
                        'motivo': f'API retornou status {response.status_code}',
                        'erro': response.text[:200]
                    },
                    'tempo_consulta_ms': tempo_ms
                }
        
        except requests.exceptions.Timeout:
            # Timeout: fallback
            tempo_ms = int((datetime.now() - inicio).total_seconds() * 1000)
            return {
                'score': MaxMindService.SCORE_NEUTRO,
                'risk_score': MaxMindService.SCORE_NEUTRO / 100,
                'fonte': 'fallback',
                'detalhes': {'motivo': 'Timeout na consulta MaxMind (>3s)'},
                'tempo_consulta_ms': tempo_ms
            }
        
        except Exception as e:
            # Erro inesperado: fallback
            tempo_ms = int((datetime.now() - inicio).total_seconds() * 1000)
            return {
                'score': MaxMindService.SCORE_NEUTRO,
                'risk_score': MaxMindService.SCORE_NEUTRO / 100,
                'fonte': 'fallback',
                'detalhes': {
                    'motivo': 'Erro na consulta MaxMind',
                    'erro': str(e)[:200]
                },
                'tempo_consulta_ms': tempo_ms
            }
    
    @staticmethod
    def limpar_cache(cpf: str = None, valor: Decimal = None, ip: str = None):
        """
        Limpa cache de consultas MaxMind
        
        Args:
            cpf: Se informado, limpa apenas cache deste CPF
            valor: Se informado junto com CPF, limpa cache específico
            ip: Se informado, limpa cache com este IP
        """
        if cpf and valor:
            cache_key = MaxMindService._get_cache_key(cpf, valor, ip)
            cache.delete(cache_key)
        elif cpf:
            # Limpar todos os caches deste CPF (pattern matching)
            # Redis não suporta pattern delete nativamente via Django cache
            # Implementação simplificada: apenas invalida cache específico se tiver valor
            pass
    
    @staticmethod
    def obter_estatisticas_cache() -> Dict[str, Any]:
        """
        Retorna estatísticas de uso do cache
        
        Returns:
            Dict com estatísticas (se disponível)
        """
        # Django cache padrão não expõe estatísticas facilmente
        # Retorna informações básicas
        return {
            'cache_timeout': MaxMindService.CACHE_TIMEOUT,
            'score_neutro': MaxMindService.SCORE_NEUTRO,
            'api_url': MaxMindService.API_URL
        }
