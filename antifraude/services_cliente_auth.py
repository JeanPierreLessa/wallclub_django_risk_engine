"""
Service para consultar dados de autenticação do cliente no Django
Integração entre riskengine e wallclub_django
"""
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from wallclub_core.oauth.services import OAuthService
import logging

logger = logging.getLogger(__name__)


def registrar_log(modulo, mensagem, nivel='INFO'):
    """Wrapper para logging"""
    if nivel == 'ERROR':
        logger.error(f"[{modulo}] {mensagem}")
    elif nivel == 'WARNING':
        logger.warning(f"[{modulo}] {mensagem}")
    else:
        logger.info(f"[{modulo}] {mensagem}")


class ClienteAutenticacaoService:
    """
    Service para consultar histórico de autenticação do cliente
    Usa OAuth 2.0 para comunicação com wallclub_django
    """
    
    # Configurações (devem vir do .env em produção)
    DJANGO_BASE_URL = 'http://wallclub-prod-release300:8003'  # Container Django
    TIMEOUT_SEGUNDOS = 2  # Timeout da requisição
    
    @classmethod
    def consultar_historico_autenticacao(cls, cpf: str, canal_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Consulta histórico de autenticação do cliente no Django
        
        Args:
            cpf: CPF do cliente (11 dígitos)
            canal_id: Canal opcional
        
        Returns:
            dict: Dados de autenticação ou None se falhar
        """
        try:
            # Importar ConfiguracaoAntifraude para buscar timeout configurado
            from antifraude.models_config import ConfiguracaoAntifraude
            timeout = ConfiguracaoAntifraude.get_config('CONSULTA_AUTH_TIMEOUT_SEGUNDOS', cls.TIMEOUT_SEGUNDOS)
            
            # Obter token OAuth
            access_token = OAuthService.get_oauth_token()
            if not access_token:
                registrar_log(
                    'antifraude.cliente_auth',
                    'Falha ao obter token OAuth',
                    nivel='ERROR'
                )
                return cls._retornar_resposta_fallback(cpf, 'falha_oauth')
            
            # Montar URL
            url = f"{cls.DJANGO_BASE_URL}/cliente/api/v1/autenticacao/analise/{cpf}/"
            
            # Query params
            params = {}
            if canal_id:
                params['canal_id'] = canal_id
            
            # Headers
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Fazer requisição
            registrar_log(
                'antifraude.cliente_auth',
                f"Consultando autenticação: CPF {cpf[:3]}*** - URL: {url}",
                nivel='DEBUG'
            )
            
            inicio = datetime.now()
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=timeout
            )
            tempo_ms = int((datetime.now() - inicio).total_seconds() * 1000)
            
            # Verificar status
            if response.status_code == 200:
                dados = response.json()
                registrar_log(
                    'antifraude.cliente_auth',
                    f"Consulta OK: CPF {cpf[:3]}*** - Encontrado: {dados.get('encontrado')} - Tempo: {tempo_ms}ms",
                    nivel='INFO'
                )
                return dados
            
            elif response.status_code == 404:
                registrar_log(
                    'antifraude.cliente_auth',
                    f"Cliente não encontrado: CPF {cpf[:3]}***",
                    nivel='WARNING'
                )
                return cls._retornar_resposta_fallback(cpf, 'cliente_nao_encontrado')
            
            else:
                registrar_log(
                    'antifraude.cliente_auth',
                    f"Erro na consulta: Status {response.status_code}",
                    nivel='ERROR'
                )
                return cls._retornar_resposta_fallback(cpf, f'http_error_{response.status_code}')
        
        except requests.Timeout:
            registrar_log(
                'antifraude.cliente_auth',
                f"Timeout ao consultar autenticação: CPF {cpf[:3]}***",
                nivel='ERROR'
            )
            return cls._retornar_resposta_fallback(cpf, 'timeout')
        
        except requests.RequestException as e:
            registrar_log(
                'antifraude.cliente_auth',
                f"Erro de conexão: {str(e)}",
                nivel='ERROR'
            )
            return cls._retornar_resposta_fallback(cpf, 'erro_conexao')
        
        except Exception as e:
            registrar_log(
                'antifraude.cliente_auth',
                f"Erro inesperado ao consultar autenticação: {str(e)}",
                nivel='ERROR'
            )
            return cls._retornar_resposta_fallback(cpf, 'erro_inesperado')
    
    @classmethod
    def _retornar_resposta_fallback(cls, cpf: str, motivo: str) -> Dict[str, Any]:
        """
        Retorna resposta de fallback quando consulta falha
        
        Args:
            cpf: CPF do cliente
            motivo: Motivo da falha
        
        Returns:
            dict: Resposta vazia com flag de falha
        """
        return {
            'encontrado': False,
            'cpf': cpf,
            'falha_consulta': True,
            'motivo_falha': motivo,
            'status_autenticacao': {
                'bloqueado': False,
                'tentativas_15min': 0,
                'tentativas_1h': 0,
                'tentativas_24h': 0
            },
            'historico_recente': {
                'total_tentativas': 0,
                'tentativas_falhas': 0,
                'taxa_falha': 0.0,
                'ips_distintos': 0,
                'devices_distintos': 0
            },
            'dispositivos_conhecidos': [],
            'bloqueios_historico': [],
            'flags_risco': []
        }
    
    @classmethod
    def calcular_score_autenticacao(cls, dados_auth: Dict[str, Any]) -> int:
        """
        Calcula score de risco baseado em dados de autenticação
        
        Args:
            dados_auth: Dados retornados por consultar_historico_autenticacao
        
        Returns:
            int: Score de 0-50 (ajuste ao score base MaxMind)
        """
        from antifraude.models_config import ConfiguracaoAntifraude
        
        score = 0
        
        # Se consulta falhou, retornar score neutro
        if dados_auth.get('falha_consulta'):
            return 0
        
        # Cliente não encontrado = sem histórico = score neutro
        if not dados_auth.get('encontrado'):
            return 0
        
        flags = dados_auth.get('flags_risco', [])
        status = dados_auth.get('status_autenticacao', {})
        historico = dados_auth.get('historico_recente', {})
        bloqueios = dados_auth.get('bloqueios_historico', [])
        
        # Buscar configurações
        max_tentativas_falhas = ConfiguracaoAntifraude.get_config('AUTH_MAX_TENTATIVAS_FALHAS_24H', 5)
        taxa_falha_suspeita = ConfiguracaoAntifraude.get_config('AUTH_TAXA_FALHA_SUSPEITA', 0.3)
        max_bloqueios = ConfiguracaoAntifraude.get_config('AUTH_MAX_BLOQUEIOS_30_DIAS', 2)
        
        # 1. Conta bloqueada agora = +30 pontos
        if status.get('bloqueado'):
            score += 30
            registrar_log('antifraude.cliente_auth', "Score +30: Conta bloqueada", nivel='DEBUG')
        
        # 2. Bloqueio recente = +20 pontos
        if 'bloqueio_recente' in flags:
            score += 20
            registrar_log('antifraude.cliente_auth', "Score +20: Bloqueio recente", nivel='DEBUG')
        
        # 3. Múltiplos bloqueios (2+) = +15 pontos
        if len(bloqueios) >= max_bloqueios:
            score += 15
            registrar_log('antifraude.cliente_auth', f"Score +15: {len(bloqueios)} bloqueios", nivel='DEBUG')
        
        # 4. Alta taxa de falha (30%+) = +15 pontos
        if historico.get('taxa_falha', 0) >= taxa_falha_suspeita:
            score += 15
            registrar_log('antifraude.cliente_auth', f"Score +15: Taxa falha {historico.get('taxa_falha')}", nivel='DEBUG')
        
        # 5. Múltiplas tentativas falhas (5+) = +10 pontos
        if historico.get('tentativas_falhas', 0) >= max_tentativas_falhas:
            score += 10
            registrar_log('antifraude.cliente_auth', f"Score +10: {historico.get('tentativas_falhas')} falhas", nivel='DEBUG')
        
        # 6. Múltiplos IPs (3+) = +10 pontos
        if 'multiplos_ips_recentes' in flags:
            score += 10
            registrar_log('antifraude.cliente_auth', "Score +10: Múltiplos IPs", nivel='DEBUG')
        
        # 7. Múltiplos dispositivos (2+) = +10 pontos
        if 'multiplos_devices_recentes' in flags:
            score += 10
            registrar_log('antifraude.cliente_auth', "Score +10: Múltiplos dispositivos", nivel='DEBUG')
        
        # 8. Todos dispositivos novos = +10 pontos
        if 'todos_devices_novos' in flags:
            score += 10
            registrar_log('antifraude.cliente_auth', "Score +10: Todos devices novos", nivel='DEBUG')
        
        # 9. Nenhum dispositivo confiável = +5 pontos
        if 'nenhum_device_confiavel' in flags:
            score += 5
            registrar_log('antifraude.cliente_auth', "Score +5: Nenhum device confiável", nivel='DEBUG')
        
        # Limitar score máximo
        score = min(score, 50)
        
        registrar_log(
            'antifraude.cliente_auth',
            f"Score autenticação calculado: {score} - Flags: {len(flags)}",
            nivel='INFO'
        )
        
        return score
