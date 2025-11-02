"""
Services para Sistema Antifraude
Fase 2 - Semana 7-9
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from decimal import Decimal
from django.db import models
from .models import TransacaoRisco, DecisaoAntifraude, RegraAntifraude
import logging

logger = logging.getLogger(__name__)

def registrar_log(modulo, mensagem, nivel='INFO'):
    """Wrapper para logging"""
    if nivel == 'ERROR':
        logger.error(f"[{modulo}] {mensagem}")
    else:
        logger.info(f"[{modulo}] {mensagem}")


class ColetaDadosService:
    """
    Normaliza dados de transações de diferentes origens (POS, App, Web)
    em formato único para análise de risco
    """
    
    @staticmethod
    def normalizar_transacao_pos(dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza dados de transação POS
        
        Args:
            dados: {
                'nsu': str,
                'cliente_id': int,
                'cpf': str,
                'valor': float,
                'modalidade': str,
                'parcelas': int,
                'terminal': str,
                'loja_id': int,
                'canal_id': int,
                'bin_cartao': str (opcional),
                'bandeira': str (opcional),
                'data_transacao': datetime
            }
        
        Returns:
            dict: Dados normalizados
        """
        return {
            'transacao_id': dados.get('nsu'),
            'origem': 'POS',
            'cliente_id': dados.get('cliente_id'),
            'cpf': dados.get('cpf'),
            'cliente_nome': dados.get('cliente_nome'),
            'valor': dados.get('valor'),
            'modalidade': dados.get('modalidade', '').upper(),
            'parcelas': dados.get('parcelas', 1),
            'ip_address': None,  # POS não tem IP
            'device_fingerprint': dados.get('terminal'),  # Terminal como fingerprint
            'user_agent': f"POS Terminal {dados.get('terminal', '')}",
            'bin_cartao': dados.get('bin_cartao'),
            'bandeira': dados.get('bandeira'),
            'loja_id': dados.get('loja_id'),
            'canal_id': dados.get('canal_id'),
            'terminal': dados.get('terminal'),
            'data_transacao': dados.get('data_transacao', datetime.now())
        }
    
    @staticmethod
    def normalizar_transacao_app(dados: Dict[str, Any], request=None) -> Dict[str, Any]:
        """
        Normaliza dados de transação App Mobile
        
        Args:
            dados: {
                'order_id': str,
                'cliente_id': int,
                'cpf': str,
                'valor': float,
                'modalidade': str,
                'parcelas': int,
                'canal_id': int,
                'bin_cartao': str (opcional),
                'bandeira': str (opcional)
            }
            request: Django request object (para extrair IP, User-Agent, etc)
        
        Returns:
            dict: Dados normalizados
        """
        # Extrair dados do request se disponível
        ip_address = None
        user_agent = None
        device_fingerprint = None
        
        if request:
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT')
            
            # Device fingerprint do OAuth se disponível
            if hasattr(request, 'oauth_token'):
                device_fingerprint = request.oauth_token.device_fingerprint
        
        return {
            'transacao_id': dados.get('order_id'),
            'origem': 'APP',
            'cliente_id': dados.get('cliente_id'),
            'cpf': dados.get('cpf'),
            'cliente_nome': dados.get('cliente_nome'),
            'valor': dados.get('valor'),
            'modalidade': dados.get('modalidade', '').upper(),
            'parcelas': dados.get('parcelas', 1),
            'ip_address': ip_address,
            'device_fingerprint': device_fingerprint,
            'user_agent': user_agent,
            'bin_cartao': dados.get('bin_cartao'),
            'bandeira': dados.get('bandeira'),
            'loja_id': None,  # App não tem loja física
            'canal_id': dados.get('canal_id'),
            'terminal': None,
            'data_transacao': dados.get('data_transacao', datetime.now())
        }
    
    @staticmethod
    def normalizar_transacao_web(dados: Dict[str, Any], request=None) -> Dict[str, Any]:
        """
        Normaliza dados de transação Web (Checkout)
        
        Args:
            dados: {
                'link_pagamento_id': str,
                'cliente_id': int,
                'cpf': str,
                'valor': float,
                'modalidade': str,
                'parcelas': int,
                'loja_id': int,
                'canal_id': int,
                'bin_cartao': str (opcional),
                'bandeira': str (opcional)
            }
            request: Django request object
        
        Returns:
            dict: Dados normalizados
        """
        # Extrair dados do request
        ip_address = None
        user_agent = None
        device_fingerprint = None
        
        if request:
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT')
            
            # Gerar device fingerprint do request
            from wallclub_core.oauth.services import OAuthService
            device_fingerprint = OAuthService.extract_device_fingerprint(request)
        
        return {
            'transacao_id': f"WEB_{dados.get('link_pagamento_id')}",
            'origem': 'WEB',
            'cliente_id': dados.get('cliente_id'),
            'cpf': dados.get('cpf'),
            'cliente_nome': dados.get('cliente_nome'),
            'valor': dados.get('valor'),
            'modalidade': dados.get('modalidade', '').upper(),
            'parcelas': dados.get('parcelas', 1),
            'ip_address': ip_address,
            'device_fingerprint': device_fingerprint,
            'user_agent': user_agent,
            'bin_cartao': dados.get('bin_cartao'),
            'bandeira': dados.get('bandeira'),
            'loja_id': dados.get('loja_id'),
            'canal_id': dados.get('canal_id'),
            'terminal': None,
            'data_transacao': dados.get('data_transacao', datetime.now())
        }
    
    @staticmethod
    def registrar_transacao(dados_normalizados: Dict[str, Any]) -> TransacaoRisco:
        """
        Registra transação normalizada no banco
        
        Args:
            dados_normalizados: Dados já normalizados por um dos métodos acima
        
        Returns:
            TransacaoRisco: Objeto criado
        """
        try:
            transacao = TransacaoRisco.objects.create(**dados_normalizados)
            
            registrar_log(
                'antifraude.coleta',
                f"Transação registrada: {transacao.origem} - {transacao.transacao_id} - R$ {transacao.valor}"
            )
            
            return transacao
            
        except Exception as e:
            registrar_log(
                'antifraude.coleta',
                f"Erro ao registrar transação: {str(e)}",
                nivel='ERROR'
            )
            raise


class AnaliseRiscoService:
    """
    Motor de análise de risco
    Avalia transações com base em regras configuradas
    """
    
    @staticmethod
    def analisar_transacao(transacao: TransacaoRisco) -> DecisaoAntifraude:
        """
        Analisa transação e retorna decisão
        Usa MaxMind como score base + regras internas para ajuste
        
        Args:
            transacao: TransacaoRisco a ser analisada
        
        Returns:
            DecisaoAntifraude: Decisão tomada
        """
        inicio = datetime.now()
        
        # 0. VERIFICAR BLACKLIST (prioridade máxima - bloqueia imediatamente)
        from .models import BlacklistAntifraude
        bloqueios = AnaliseRiscoService._verificar_blacklist(transacao)
        
        if bloqueios:
            # BLACKLIST = REPROVAÇÃO IMEDIATA
            tempo_analise = int((datetime.now() - inicio).total_seconds() * 1000)
            motivo_bloqueio = "; ".join([f"{b['tipo']}: {b['motivo']}" for b in bloqueios])
            
            decisao = DecisaoAntifraude.objects.create(
                transacao=transacao,
                score_risco=100,  # Score máximo
                decisao='REPROVADO',
                regras_acionadas=[{
                    'nome': 'Blacklist',
                    'tipo': 'BLACKLIST',
                    'peso': 10,
                    'acao': 'REPROVAR',
                    'detalhes': bloqueios
                }],
                motivo=f"BLACKLIST ATIVA: {motivo_bloqueio}",
                tempo_analise_ms=tempo_analise
            )
            
            registrar_log(
                'antifraude.blacklist',
                f"BLOQUEADO por blacklist: {transacao.transacao_id} - {motivo_bloqueio}"
            )
            
            return decisao
        
        # VERIFICAR WHITELIST (reduz score base)
        from .models_config import ConfiguracaoAntifraude
        
        whitelists = AnaliseRiscoService._verificar_whitelist(transacao)
        desconto_whitelist = 0
        
        if whitelists:
            # Buscar configurações de whitelist
            desconto_por_item = ConfiguracaoAntifraude.get_config('SCORE_DESCONTO_WHITELIST', 20)
            desconto_max = ConfiguracaoAntifraude.get_config('SCORE_DESCONTO_MAX_WHITELIST', 40)
            
            desconto_whitelist = min(len(whitelists) * desconto_por_item, desconto_max)
            registrar_log(
                'antifraude.whitelist',
                f"Whitelist encontrada: {transacao.transacao_id} - Desconto: -{desconto_whitelist} pontos"
            )
        
        # 1. Consultar MaxMind para score base
        from .services_maxmind import MaxMindService
        
        dados_transacao = {
            'transacao_id': transacao.transacao_id,
            'cliente_id': transacao.cliente_id,
            'cpf': transacao.cpf,
            'cliente_nome': transacao.cliente_nome,
            'valor': transacao.valor,
            'modalidade': transacao.modalidade,
            'ip_address': transacao.ip_address,
            'user_agent': transacao.user_agent,
            'device_fingerprint': transacao.device_fingerprint,
            'bin_cartao': transacao.bin_cartao,
            'loja_id': transacao.loja_id
        }
        
        resultado_maxmind = MaxMindService.consultar_score(dados_transacao)
        score_total = resultado_maxmind['score']
        
        registrar_log(
            'antifraude.maxmind',
            f"MaxMind score: {score_total} (fonte: {resultado_maxmind['fonte']}) - {resultado_maxmind['tempo_consulta_ms']}ms"
        )
        
        # Inicializar lista de regras acionadas e motivos
        regras_acionadas = [{
            'nome': 'MaxMind minFraud',
            'tipo': 'SCORE_EXTERNO',
            'peso': resultado_maxmind['score'],
            'acao': 'ALERTAR',
            'detalhes': resultado_maxmind['detalhes']
        }]
        motivos = [f"Score MaxMind: {resultado_maxmind['score']} ({resultado_maxmind['fonte']})"]
        
        # 2. Aplicar desconto de whitelist no score base
        if desconto_whitelist > 0:
            score_total = max(0, score_total - desconto_whitelist)
            regras_acionadas.append({
                'nome': 'Whitelist',
                'tipo': 'WHITELIST',
                'peso': -desconto_whitelist,
                'acao': 'APROVAR',
                'detalhes': whitelists
            })
            motivos.append(f"Whitelist: -{desconto_whitelist} pontos")
            registrar_log(
                'antifraude.whitelist',
                f"Score ajustado: {score_total} (desconto de {desconto_whitelist} pontos)"
            )
        
        # 2.5. ENRIQUECER COM DADOS DE AUTENTICAÇÃO
        from .services_cliente_auth import ClienteAutenticacaoService
        
        dados_auth = ClienteAutenticacaoService.consultar_historico_autenticacao(
            cpf=transacao.cpf,
            canal_id=transacao.canal_id
        )
        
        score_auth = ClienteAutenticacaoService.calcular_score_autenticacao(dados_auth)
        
        if score_auth > 0:
            score_total += score_auth
            regras_acionadas.append({
                'nome': 'Análise de Autenticação',
                'tipo': 'AUTENTICACAO',
                'peso': score_auth,
                'acao': 'ALERTAR' if score_auth < 30 else 'REVISAR',
                'detalhes': {
                    'flags_risco': dados_auth.get('flags_risco', []),
                    'bloqueado': dados_auth.get('status_autenticacao', {}).get('bloqueado', False),
                    'tentativas_falhas_24h': dados_auth.get('historico_recente', {}).get('tentativas_falhas', 0)
                }
            })
            motivos.append(f"Score autenticação: +{score_auth} pontos")
            registrar_log(
                'antifraude.autenticacao',
                f"Score autenticação: +{score_auth} - Flags: {len(dados_auth.get('flags_risco', []))}"
            )
        
        # 3. Buscar regras ativas ordenadas por prioridade
        regras = RegraAntifraude.objects.filter(is_active=True).order_by('prioridade')
        decisao_final = 'APROVADO'
        
        # 3. Executar regras internas (ajustam score MaxMind)
        for regra in regras:
            resultado = AnaliseRiscoService._executar_regra(regra, transacao)
            
            if resultado['acionada']:
                ajuste_score = regra.peso * 5  # Peso 1-10 → Ajuste 5-50 pontos
                score_total += ajuste_score
                
                regras_acionadas.append({
                    'nome': regra.nome,
                    'tipo': regra.tipo,
                    'peso': regra.peso,
                    'acao': regra.acao,
                    'ajuste_score': ajuste_score,
                    'detalhes': resultado['detalhes']
                })
                motivos.append(f"{regra.nome}: {resultado['motivo']}")
                
                # Atualizar decisão baseado na ação mais restritiva
                if regra.acao == 'REPROVAR':
                    decisao_final = 'REPROVADO'
                elif regra.acao == 'REVISAR' and decisao_final != 'REPROVADO':
                    decisao_final = 'REVISAO'
        
        # 4. Limitar score a 100
        score_total = min(score_total, 100)
        
        # 5. Decisão final baseada em thresholds (usa configurações)
        from .models_config import ConfiguracaoAntifraude
        
        limite_aprovacao = ConfiguracaoAntifraude.get_config('SCORE_LIMITE_APROVACAO_AUTO', 30)
        limite_revisao = ConfiguracaoAntifraude.get_config('SCORE_LIMITE_REVISAO', 31)
        limite_reprovacao = ConfiguracaoAntifraude.get_config('SCORE_LIMITE_REPROVACAO', 70)
        
        if score_total >= limite_reprovacao and decisao_final != 'REPROVADO':
            decisao_final = 'REPROVADO'
            motivos.append(f'Score crítico (>={limite_reprovacao})')
        elif score_total >= limite_revisao and decisao_final == 'APROVADO':
            decisao_final = 'REVISAO'
            motivos.append(f'Score alto (>={limite_revisao}) - requer revisão')
        
        # Calcular tempo de análise
        tempo_analise = int((datetime.now() - inicio).total_seconds() * 1000)
        
        # Criar decisão
        decisao = DecisaoAntifraude.objects.create(
            transacao=transacao,
            score_risco=score_total,
            decisao=decisao_final,
            regras_acionadas=regras_acionadas,
            motivo="; ".join(motivos),
            tempo_analise_ms=tempo_analise
        )
        
        registrar_log(
            'antifraude.analise',
            f"Análise concluída: {transacao.transacao_id} - {decisao_final} - Score: {score_total} - {tempo_analise}ms"
        )
        
        # Notificar se precisa revisão manual
        if decisao_final == 'REVISAO':
            try:
                from .notifications import NotificacaoService
                NotificacaoService.notificar_revisao_pendente(decisao)
            except Exception as e:
                registrar_log('antifraude.notificacao', f"Erro ao notificar: {str(e)}", nivel='ERROR')
        
        # Verificar whitelist automática se APROVADO
        if decisao_final == 'APROVADO':
            try:
                from .services_whitelist import WhitelistAutoService
                WhitelistAutoService.verificar_e_criar_whitelist(transacao, decisao)
            except Exception as e:
                registrar_log('antifraude.whitelist_auto', f"Erro ao verificar whitelist automática: {str(e)}", nivel='ERROR')
        
        return decisao
    
    @staticmethod
    def _executar_regra(regra: RegraAntifraude, transacao: TransacaoRisco) -> Dict[str, Any]:
        """
        Executa regra específica
        
        Returns:
            dict: {'acionada': bool, 'motivo': str, 'detalhes': dict}
        """
        try:
            parametros = regra.parametros
            
            if regra.tipo == 'VELOCIDADE':
                return AnaliseRiscoService._regra_velocidade(parametros, transacao)
            
            elif regra.tipo == 'VALOR':
                return AnaliseRiscoService._regra_valor(parametros, transacao)
            
            elif regra.tipo == 'DISPOSITIVO':
                return AnaliseRiscoService._regra_dispositivo(parametros, transacao)
            
            elif regra.tipo == 'HORARIO':
                return AnaliseRiscoService._regra_horario(parametros, transacao)
            
            elif regra.tipo == 'LOCALIZACAO':
                return AnaliseRiscoService._regra_localizacao(parametros, transacao)
            
            else:
                return {'acionada': False, 'motivo': 'Tipo de regra não implementado', 'detalhes': {}}
        
        except Exception as e:
            registrar_log('antifraude.regra', f"Erro ao executar regra {regra.nome}: {str(e)}", nivel='ERROR')
            return {'acionada': False, 'motivo': f'Erro: {str(e)}', 'detalhes': {}}
    
    @staticmethod
    def _regra_velocidade(parametros: Dict, transacao: TransacaoRisco) -> Dict[str, Any]:
        """Regra: Múltiplas transações em curto período"""
        max_transacoes = parametros.get('max_transacoes', 3)
        janela_minutos = parametros.get('janela_minutos', 10)
        
        janela_inicio = transacao.data_transacao - timedelta(minutes=janela_minutos)
        
        count = TransacaoRisco.objects.filter(
            cpf=transacao.cpf,
            data_transacao__gte=janela_inicio,
            data_transacao__lte=transacao.data_transacao
        ).count()
        
        if count > max_transacoes:
            return {
                'acionada': True,
                'motivo': f'{count} transações em {janela_minutos} minutos',
                'detalhes': {'count': count, 'janela_minutos': janela_minutos}
            }
        
        return {'acionada': False, 'motivo': '', 'detalhes': {}}
    
    @staticmethod
    def _regra_valor(parametros: Dict, transacao: TransacaoRisco) -> Dict[str, Any]:
        """Regra: Valor muito acima da média do cliente"""
        multiplicador = parametros.get('multiplicador_media', 3)
        
        # Calcular média dos últimos 30 dias
        media = TransacaoRisco.objects.filter(
            cliente_id=transacao.cliente_id,
            data_transacao__gte=transacao.data_transacao - timedelta(days=30)
        ).aggregate(models.Avg('valor'))['valor__avg'] or 0
        
        if media > 0 and transacao.valor > (media * multiplicador):
            return {
                'acionada': True,
                'motivo': f'Valor R$ {transacao.valor} é {multiplicador}x maior que média R$ {media:.2f}',
                'detalhes': {'valor': float(transacao.valor), 'media': float(media), 'multiplicador': multiplicador}
            }
        
        return {'acionada': False, 'motivo': '', 'detalhes': {}}
    
    @staticmethod
    def _regra_dispositivo(parametros: Dict, transacao: TransacaoRisco) -> Dict[str, Any]:
        """Regra: Dispositivo nunca usado pelo cliente"""
        if not transacao.device_fingerprint:
            return {'acionada': False, 'motivo': '', 'detalhes': {}}
        
        ja_usado = TransacaoRisco.objects.filter(
            cliente_id=transacao.cliente_id,
            device_fingerprint=transacao.device_fingerprint
        ).exclude(id=transacao.id).exists()
        
        if not ja_usado:
            return {
                'acionada': True,
                'motivo': 'Primeiro uso deste dispositivo',
                'detalhes': {'device_fingerprint': transacao.device_fingerprint}
            }
        
        return {'acionada': False, 'motivo': '', 'detalhes': {}}
    
    @staticmethod
    def _regra_horario(parametros: Dict, transacao: TransacaoRisco) -> Dict[str, Any]:
        """Regra: Horário suspeito (madrugada)"""
        hora_inicio = parametros.get('hora_inicio', 0)
        hora_fim = parametros.get('hora_fim', 5)
        
        hora_transacao = transacao.data_transacao.hour
        
        if hora_inicio <= hora_transacao < hora_fim:
            return {
                'acionada': True,
                'motivo': f'Transação às {hora_transacao}h (horário suspeito)',
                'detalhes': {'hora': hora_transacao}
            }
        
        return {'acionada': False, 'motivo': '', 'detalhes': {}}
    
    @staticmethod
    def _regra_localizacao(parametros: Dict, transacao: TransacaoRisco) -> Dict[str, Any]:
        """Regra: Múltiplos CPFs no mesmo IP"""
        if not transacao.ip_address:
            return {'acionada': False, 'motivo': '', 'detalhes': {}}
        
        max_cpfs = parametros.get('max_cpfs_por_ip', 5)
        janela_horas = parametros.get('janela_horas', 24)
        
        janela_inicio = transacao.data_transacao - timedelta(hours=janela_horas)
        
        cpfs_distintos = TransacaoRisco.objects.filter(
            ip_address=transacao.ip_address,
            data_transacao__gte=janela_inicio
        ).values('cpf').distinct().count()
        
        if cpfs_distintos > max_cpfs:
            return {
                'acionada': True,
                'motivo': f'{cpfs_distintos} CPFs diferentes no IP {transacao.ip_address}',
                'detalhes': {'cpfs_count': cpfs_distintos, 'ip': transacao.ip_address}
            }
        
        return {'acionada': False, 'motivo': '', 'detalhes': {}}
    
    @staticmethod
    def _verificar_blacklist(transacao: TransacaoRisco) -> list:
        """
        Verifica se transação está em blacklist
        Retorna lista de bloqueios encontrados
        """
        from .models import BlacklistAntifraude
        
        bloqueios = []
        agora = datetime.now()
        
        # Verificar CPF
        if transacao.cpf:
            bloqueio_cpf = BlacklistAntifraude.objects.filter(
                tipo='CPF',
                valor=transacao.cpf,
                is_active=True
            ).filter(
                models.Q(permanente=True) | models.Q(data_expiracao__gt=agora)
            ).first()
            
            if bloqueio_cpf:
                bloqueios.append({
                    'tipo': 'CPF',
                    'valor': transacao.cpf,
                    'motivo': bloqueio_cpf.motivo,
                    'permanente': bloqueio_cpf.permanente
                })
        
        # Verificar IP
        if transacao.ip_address:
            bloqueio_ip = BlacklistAntifraude.objects.filter(
                tipo='IP',
                valor=str(transacao.ip_address),
                is_active=True
            ).filter(
                models.Q(permanente=True) | models.Q(data_expiracao__gt=agora)
            ).first()
            
            if bloqueio_ip:
                bloqueios.append({
                    'tipo': 'IP',
                    'valor': str(transacao.ip_address),
                    'motivo': bloqueio_ip.motivo,
                    'permanente': bloqueio_ip.permanente
                })
        
        # Verificar Device
        if transacao.device_fingerprint:
            bloqueio_device = BlacklistAntifraude.objects.filter(
                tipo='DEVICE',
                valor=transacao.device_fingerprint,
                is_active=True
            ).filter(
                models.Q(permanente=True) | models.Q(data_expiracao__gt=agora)
            ).first()
            
            if bloqueio_device:
                bloqueios.append({
                    'tipo': 'DEVICE',
                    'valor': transacao.device_fingerprint,
                    'motivo': bloqueio_device.motivo,
                    'permanente': bloqueio_device.permanente
                })
        
        # Verificar BIN do cartão
        if transacao.bin_cartao:
            bloqueio_bin = BlacklistAntifraude.objects.filter(
                tipo='BIN',
                valor=transacao.bin_cartao,
                is_active=True
            ).filter(
                models.Q(permanente=True) | models.Q(data_expiracao__gt=agora)
            ).first()
            
            if bloqueio_bin:
                bloqueios.append({
                    'tipo': 'BIN',
                    'valor': transacao.bin_cartao,
                    'motivo': bloqueio_bin.motivo,
                    'permanente': bloqueio_bin.permanente
                })
        
        return bloqueios
    
    @staticmethod
    def _verificar_whitelist(transacao: TransacaoRisco) -> list:
        """
        Verifica se transação está em whitelist
        Retorna lista de whitelists encontradas
        """
        from .models import WhitelistAntifraude
        
        whitelists = []
        
        # Verificar CPF
        if transacao.cpf:
            whitelist_cpf = WhitelistAntifraude.objects.filter(
                tipo='CPF',
                valor=transacao.cpf,
                is_active=True
            ).first()
            
            if whitelist_cpf:
                whitelists.append({
                    'tipo': 'CPF',
                    'valor': transacao.cpf,
                    'origem': whitelist_cpf.origem,
                    'transacoes_aprovadas': whitelist_cpf.transacoes_aprovadas
                })
        
        # Verificar IP
        if transacao.ip_address:
            whitelist_ip = WhitelistAntifraude.objects.filter(
                tipo='IP',
                valor=str(transacao.ip_address),
                is_active=True
            ).first()
            
            if whitelist_ip:
                whitelists.append({
                    'tipo': 'IP',
                    'valor': str(transacao.ip_address),
                    'origem': whitelist_ip.origem
                })
        
        # Verificar Device
        if transacao.device_fingerprint:
            whitelist_device = WhitelistAntifraude.objects.filter(
                tipo='DEVICE',
                valor=transacao.device_fingerprint,
                is_active=True
            ).first()
            
            if whitelist_device:
                whitelists.append({
                    'tipo': 'DEVICE',
                    'valor': transacao.device_fingerprint,
                    'origem': whitelist_device.origem
                })
        
        return whitelists
