"""
Auth3DS Service - Integração com Gateway 3D Secure
Fase 2 - Semana 13

Implementa autenticação 3DS 2.0 para transações com cartão de crédito.
O 3DS adiciona uma camada extra de segurança validando o titular do cartão
através do banco emissor.
"""
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
import requests
import hashlib
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def registrar_log(modulo, mensagem, nivel='INFO'):
    """Wrapper para logging"""
    if nivel == 'ERROR':
        logger.error(f"[{modulo}] {mensagem}")
    else:
        logger.info(f"[{modulo}] {mensagem}")


class Auth3DSService:
    """
    Service para autenticação 3D Secure 2.0
    
    Fluxo 3DS:
    1. Verificar elegibilidade do cartão (enrolled)
    2. Iniciar autenticação no banco emissor
    3. Cliente completa desafio (SMS, app banco, etc)
    4. Validar resultado da autenticação
    5. Usar CAVV/ECI na transação final
    
    Configurações necessárias (settings.py):
    - THREEDS_GATEWAY_URL
    - THREEDS_MERCHANT_ID
    - THREEDS_MERCHANT_KEY
    - THREEDS_ENABLED (True/False)
    """
    
    def __init__(self):
        self.gateway_url = getattr(settings, 'THREEDS_GATEWAY_URL', None)
        self.merchant_id = getattr(settings, 'THREEDS_MERCHANT_ID', None)
        self.merchant_key = getattr(settings, 'THREEDS_MERCHANT_KEY', None)
        self.enabled = getattr(settings, 'THREEDS_ENABLED', False)
        self.timeout = getattr(settings, 'THREEDS_TIMEOUT', 30)
    
    def esta_habilitado(self) -> bool:
        """Verifica se 3DS está habilitado e configurado"""
        if not self.enabled:
            return False
        
        if not all([self.gateway_url, self.merchant_id, self.merchant_key]):
            registrar_log(
                'antifraude.3ds',
                'Configurações 3DS incompletas (gateway_url, merchant_id ou merchant_key faltando)',
                nivel='ERROR'
            )
            return False
        
        return True
    
    def verificar_elegibilidade(self, bin_cartao: str, valor: Decimal) -> Dict[str, Any]:
        """
        Verifica se cartão está inscrito no 3DS (enrolled)
        
        Args:
            bin_cartao: Primeiros 6 dígitos do cartão
            valor: Valor da transação
        
        Returns:
            {
                'elegivel': bool,
                'versao_3ds': str,  # '2.0', '1.0'
                'banco_emissor': str,
                'acs_url': str,  # URL para autenticação
                'mensagem': str
            }
        """
        if not self.esta_habilitado():
            return {
                'elegivel': False,
                'versao_3ds': None,
                'banco_emissor': None,
                'acs_url': None,
                'mensagem': '3DS não está habilitado'
            }
        
        try:
            payload = {
                'merchant_id': self.merchant_id,
                'bin': bin_cartao,
                'valor': float(valor),
                'timestamp': datetime.now().isoformat()
            }
            
            # Assinar requisição
            payload['signature'] = self._gerar_assinatura(payload)
            
            registrar_log('antifraude.3ds', f'Verificando elegibilidade BIN: {bin_cartao}')
            
            response = requests.post(
                f'{self.gateway_url}/v2/check-enrollment',
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                resultado = {
                    'elegivel': data.get('enrolled', False),
                    'versao_3ds': data.get('version', '2.0'),
                    'banco_emissor': data.get('issuer_bank', 'Desconhecido'),
                    'acs_url': data.get('acs_url'),
                    'mensagem': data.get('message', 'Cartão elegível para 3DS')
                }
                
                registrar_log(
                    'antifraude.3ds',
                    f'BIN {bin_cartao} - Elegível: {resultado["elegivel"]}'
                )
                
                return resultado
            else:
                registrar_log(
                    'antifraude.3ds',
                    f'Erro ao verificar elegibilidade: HTTP {response.status_code}',
                    nivel='ERROR'
                )
                return self._resultado_erro('Erro ao verificar elegibilidade')
        
        except requests.Timeout:
            registrar_log('antifraude.3ds', 'Timeout ao verificar elegibilidade', nivel='ERROR')
            return self._resultado_erro('Timeout na verificação')
        
        except Exception as e:
            registrar_log('antifraude.3ds', f'Exceção ao verificar elegibilidade: {str(e)}', nivel='ERROR')
            return self._resultado_erro(f'Erro: {str(e)}')
    
    def iniciar_autenticacao(
        self,
        transacao_id: str,
        bin_cartao: str,
        valor: Decimal,
        moeda: str = 'BRL',
        dados_cliente: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Inicia processo de autenticação 3DS
        
        Args:
            transacao_id: ID único da transação
            bin_cartao: BIN do cartão
            valor: Valor da transação
            moeda: Código ISO da moeda (BRL, USD, etc)
            dados_cliente: Dados do cliente para autenticação {
                'nome': str,
                'email': str,
                'telefone': str,
                'cpf': str,
                'ip_address': str,
                'user_agent': str
            }
        
        Returns:
            {
                'sucesso': bool,
                'auth_id': str,  # ID da autenticação 3DS
                'redirect_url': str,  # URL para cliente completar desafio
                'metodo': str,  # 'BROWSER', 'APP', 'OOB'
                'expiracao': datetime,
                'mensagem': str
            }
        """
        if not self.esta_habilitado():
            return self._resultado_autenticacao_erro('3DS não habilitado')
        
        try:
            payload = {
                'merchant_id': self.merchant_id,
                'transaction_id': transacao_id,
                'bin': bin_cartao,
                'valor': float(valor),
                'moeda': moeda,
                'timestamp': datetime.now().isoformat()
            }
            
            # Adicionar dados do cliente se fornecidos
            if dados_cliente:
                payload['customer'] = {
                    'name': dados_cliente.get('nome'),
                    'email': dados_cliente.get('email'),
                    'phone': dados_cliente.get('telefone'),
                    'document': dados_cliente.get('cpf'),
                    'ip': dados_cliente.get('ip_address'),
                    'user_agent': dados_cliente.get('user_agent')
                }
            
            # Assinar requisição
            payload['signature'] = self._gerar_assinatura(payload)
            
            registrar_log('antifraude.3ds', f'Iniciando autenticação 3DS: {transacao_id}')
            
            response = requests.post(
                f'{self.gateway_url}/v2/authenticate',
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                resultado = {
                    'sucesso': True,
                    'auth_id': data.get('auth_id'),
                    'redirect_url': data.get('redirect_url'),
                    'metodo': data.get('method', 'BROWSER'),
                    'expiracao': data.get('expires_at'),
                    'mensagem': 'Autenticação iniciada com sucesso'
                }
                
                registrar_log(
                    'antifraude.3ds',
                    f'3DS iniciado - Auth ID: {resultado["auth_id"]}'
                )
                
                return resultado
            else:
                registrar_log(
                    'antifraude.3ds',
                    f'Erro ao iniciar autenticação: HTTP {response.status_code}',
                    nivel='ERROR'
                )
                return self._resultado_autenticacao_erro('Erro ao iniciar autenticação')
        
        except Exception as e:
            registrar_log('antifraude.3ds', f'Exceção ao iniciar autenticação: {str(e)}', nivel='ERROR')
            return self._resultado_autenticacao_erro(f'Erro: {str(e)}')
    
    def validar_autenticacao(self, auth_id: str) -> Dict[str, Any]:
        """
        Valida resultado da autenticação 3DS após cliente completar desafio
        
        Args:
            auth_id: ID da autenticação retornado por iniciar_autenticacao()
        
        Returns:
            {
                'sucesso': bool,
                'status': str,  # 'Y' (autenticado), 'N' (falhou), 'A' (tentativa), 'U' (indisponível)
                'eci': str,  # Electronic Commerce Indicator
                'cavv': str,  # Cardholder Authentication Verification Value
                'xid': str,  # Transaction ID 3DS
                'mensagem': str
            }
        """
        if not self.esta_habilitado():
            return self._resultado_validacao_erro('3DS não habilitado')
        
        try:
            payload = {
                'merchant_id': self.merchant_id,
                'auth_id': auth_id,
                'timestamp': datetime.now().isoformat()
            }
            
            payload['signature'] = self._gerar_assinatura(payload)
            
            registrar_log('antifraude.3ds', f'Validando autenticação 3DS: {auth_id}')
            
            response = requests.get(
                f'{self.gateway_url}/v2/authenticate/{auth_id}',
                params=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                status = data.get('status')
                resultado = {
                    'sucesso': status in ['Y', 'A'],  # Y=autenticado, A=tentativa
                    'status': status,
                    'eci': data.get('eci'),
                    'cavv': data.get('cavv'),
                    'xid': data.get('xid'),
                    'mensagem': self._interpretar_status_3ds(status)
                }
                
                registrar_log(
                    'antifraude.3ds',
                    f'3DS validado - Status: {status} - Sucesso: {resultado["sucesso"]}'
                )
                
                return resultado
            else:
                registrar_log(
                    'antifraude.3ds',
                    f'Erro ao validar autenticação: HTTP {response.status_code}',
                    nivel='ERROR'
                )
                return self._resultado_validacao_erro('Erro ao validar autenticação')
        
        except Exception as e:
            registrar_log('antifraude.3ds', f'Exceção ao validar autenticação: {str(e)}', nivel='ERROR')
            return self._resultado_validacao_erro(f'Erro: {str(e)}')
    
    def recomendar_3ds(
        self,
        score_risco: int,
        valor: Decimal,
        bin_cartao: str,
        elegibilidade: Optional[Dict] = None
    ) -> Tuple[bool, str]:
        """
        Recomenda se deve usar 3DS baseado em score de risco e regras
        
        Args:
            score_risco: Score de risco (0-100)
            valor: Valor da transação
            bin_cartao: BIN do cartão
            elegibilidade: Resultado de verificar_elegibilidade() (opcional)
        
        Returns:
            (deve_usar_3ds: bool, motivo: str)
        """
        if not self.esta_habilitado():
            return False, '3DS não habilitado'
        
        # Regra 1: Score de risco alto (>60) sempre usa 3DS
        if score_risco > 60:
            return True, f'Score de risco alto ({score_risco})'
        
        # Regra 2: Valores acima de R$ 500 sempre usa 3DS
        if valor > Decimal('500.00'):
            return True, f'Valor alto (R$ {valor})'
        
        # Regra 3: Score médio (40-60) + valor médio (>R$ 200) usa 3DS
        if score_risco >= 40 and valor > Decimal('200.00'):
            return True, f'Score médio ({score_risco}) + valor médio (R$ {valor})'
        
        # Regra 4: Verificar se cartão é elegível
        if elegibilidade and not elegibilidade.get('elegivel'):
            return False, 'Cartão não elegível para 3DS'
        
        # Score baixo (<40) e valor baixo (<R$ 200) não precisa 3DS
        return False, f'Score baixo ({score_risco}) e valor baixo (R$ {valor})'
    
    def _gerar_assinatura(self, payload: Dict) -> str:
        """Gera assinatura HMAC SHA256 para requisição"""
        # Ordenar chaves para assinatura consistente
        payload_str = json.dumps(payload, sort_keys=True)
        
        assinatura = hashlib.sha256(
            f"{payload_str}{self.merchant_key}".encode()
        ).hexdigest()
        
        return assinatura
    
    def _interpretar_status_3ds(self, status: str) -> str:
        """Interpreta código de status 3DS"""
        status_map = {
            'Y': 'Autenticação bem-sucedida',
            'N': 'Autenticação falhou',
            'A': 'Tentativa de autenticação',
            'U': 'Autenticação indisponível',
            'R': 'Autenticação rejeitada',
            'C': 'Desafio necessário'
        }
        return status_map.get(status, f'Status desconhecido: {status}')
    
    def _resultado_erro(self, mensagem: str) -> Dict[str, Any]:
        """Resultado padrão para erro em verificar_elegibilidade"""
        return {
            'elegivel': False,
            'versao_3ds': None,
            'banco_emissor': None,
            'acs_url': None,
            'mensagem': mensagem
        }
    
    def _resultado_autenticacao_erro(self, mensagem: str) -> Dict[str, Any]:
        """Resultado padrão para erro em iniciar_autenticacao"""
        return {
            'sucesso': False,
            'auth_id': None,
            'redirect_url': None,
            'metodo': None,
            'expiracao': None,
            'mensagem': mensagem
        }
    
    def _resultado_validacao_erro(self, mensagem: str) -> Dict[str, Any]:
        """Resultado padrão para erro em validar_autenticacao"""
        return {
            'sucesso': False,
            'status': 'U',
            'eci': None,
            'cavv': None,
            'xid': None,
            'mensagem': mensagem
        }
