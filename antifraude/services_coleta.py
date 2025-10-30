"""
Serviço de Coleta e Normalização de Dados
Fase 2 - Semana 8: Normalização de dados POS/App/Web
"""
from decimal import Decimal
from datetime import datetime
from typing import Dict, Optional, Any
import re


class ColetaDadosService:
    """
    Normaliza dados de transações de diferentes origens (POS, App, Web)
    em formato único para análise de risco
    """
    
    @staticmethod
    def extrair_bin_cartao(numero_cartao: str) -> Optional[str]:
        """
        Extrai BIN (primeiros 6 dígitos) do número do cartão
        
        Args:
            numero_cartao: Número do cartão (pode conter espaços, hífens)
        
        Returns:
            BIN do cartão (6 dígitos) ou None
        """
        if not numero_cartao:
            return None
        
        # Remove tudo que não é dígito
        digitos = re.sub(r'\D', '', numero_cartao)
        
        # BIN = primeiros 6 dígitos
        if len(digitos) >= 6:
            return digitos[:6]
        
        return None
    
    @staticmethod
    def normalizar_origem(origem: str) -> str:
        """
        Normaliza identificador de origem para padrão
        
        Args:
            origem: Identificador original (pos, posp2, app, mobile, web, checkout)
        
        Returns:
            Origem normalizada (POS, APP, WEB)
        """
        origem_lower = origem.lower().strip()
        
        if origem_lower in ['pos', 'posp2', 'terminal']:
            return 'POS'
        elif origem_lower in ['app', 'mobile', 'aplicativo']:
            return 'APP'
        elif origem_lower in ['web', 'checkout', 'link']:
            return 'WEB'
        
        # Fallback
        return 'WEB'
    
    @staticmethod
    def normalizar_modalidade(modalidade: str) -> str:
        """
        Normaliza nome da modalidade de pagamento
        
        Args:
            modalidade: Nome original (pix, credito, debito, etc)
        
        Returns:
            Modalidade normalizada
        """
        modalidade_upper = modalidade.upper().strip()
        
        # Mapeamento de variações
        mapa = {
            'PIX': 'PIX',
            'CREDITO': 'CREDITO',
            'CRÉDITO': 'CREDITO',
            'CREDIT': 'CREDITO',
            'CREDIT_ONE_INSTALLMENT': 'CREDITO',  # Pinbank: crédito à vista
            'CREDIT_TWO_INSTALLMENTS': 'PARCELADO',  # Pinbank: parcelado 2x
            'CREDIT_WITH_INSTALLMENTS': 'PARCELADO',  # Pinbank: parcelado 3x+
            'DEBITO': 'DEBITO',
            'DÉBITO': 'DEBITO',
            'DEBIT': 'DEBITO',
            'DEBIT_CARD': 'DEBITO',  # Pinbank: débito
            'PARCELADO': 'PARCELADO',
            'INSTALLMENT': 'PARCELADO',
        }
        
        return mapa.get(modalidade_upper, modalidade_upper)
    
    @staticmethod
    def normalizar_dados_pos(dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza dados vindos do terminal POS
        
        Args:
            dados: Dict com dados do POS
                - nsu: NSU da transação
                - cpf: CPF do cliente
                - valor: Valor da transação
                - modalidade: Forma de pagamento
                - parcelas: Número de parcelas
                - numero_cartao: Número do cartão (opcional)
                - bandeira: Bandeira do cartão (opcional)
                - terminal: ID do terminal
                - loja_id: ID da loja
                - canal_id: ID do canal
        
        Returns:
            Dict normalizado para TransacaoRisco
        """
        return {
            'transacao_id': dados.get('transaction_id') or dados.get('nsu', ''),
            'origem': 'POS',
            'cliente_id': dados.get('cliente_id'),
            'cpf': dados.get('cpf', '').replace('.', '').replace('-', ''),
            'cliente_nome': dados.get('cliente_nome'),
            'valor': Decimal(str(dados.get('valor', 0))),
            'modalidade': ColetaDadosService.normalizar_modalidade(dados.get('modalidade', '')),
            'parcelas': int(dados.get('parcelas', 1)),
            'ip_address': None,  # POS geralmente não tem IP do cliente
            'device_fingerprint': dados.get('terminal'),  # Usa terminal como fingerprint
            'user_agent': None,
            'bin_cartao': ColetaDadosService.extrair_bin_cartao(dados.get('numero_cartao')),
            'bandeira': dados.get('bandeira'),
            'loja_id': dados.get('loja_id'),
            'canal_id': dados.get('canal_id'),
            'terminal': dados.get('terminal'),
            'data_transacao': dados.get('data_transacao', datetime.now()),
        }
    
    @staticmethod
    def normalizar_dados_app(dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza dados vindos do app mobile
        
        Args:
            dados: Dict com dados do app
                - transaction_id: ID da transação
                - cpf: CPF do cliente
                - valor: Valor da transação
                - modalidade: Forma de pagamento
                - parcelas: Número de parcelas
                - numero_cartao: Número do cartão (opcional)
                - bandeira: Bandeira do cartão (opcional)
                - ip_address: IP do cliente
                - device_fingerprint: Fingerprint do dispositivo
                - user_agent: User agent do app
                - loja_id: ID da loja
                - canal_id: ID do canal
        
        Returns:
            Dict normalizado para TransacaoRisco
        """
        return {
            'transacao_id': dados.get('transaction_id', dados.get('order_id', '')),
            'origem': 'APP',
            'cliente_id': dados.get('cliente_id'),
            'cpf': dados.get('cpf', '').replace('.', '').replace('-', ''),
            'cliente_nome': dados.get('cliente_nome'),
            'valor': Decimal(str(dados.get('valor', 0))),
            'modalidade': ColetaDadosService.normalizar_modalidade(dados.get('modalidade', '')),
            'parcelas': int(dados.get('parcelas', 1)),
            'ip_address': dados.get('ip_address'),
            'device_fingerprint': dados.get('device_fingerprint'),
            'user_agent': dados.get('user_agent'),
            'bin_cartao': ColetaDadosService.extrair_bin_cartao(dados.get('numero_cartao')),
            'bandeira': dados.get('bandeira'),
            'loja_id': dados.get('loja_id'),
            'canal_id': dados.get('canal_id'),
            'terminal': None,
            'data_transacao': dados.get('data_transacao', datetime.now()),
        }
    
    @staticmethod
    def normalizar_dados_web(dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza dados vindos do checkout web
        
        Args:
            dados: Dict com dados do checkout
                - order_id: ID do pedido
                - token: Token do checkout
                - cpf: CPF do cliente
                - valor: Valor da transação
                - modalidade: Forma de pagamento
                - parcelas: Número de parcelas
                - numero_cartao: Número do cartão
                - bandeira: Bandeira do cartão
                - ip_address: IP do cliente
                - user_agent: User agent do browser
                - loja_id: ID da loja
                - canal_id: ID do canal
        
        Returns:
            Dict normalizado para TransacaoRisco
        """
        # Web pode usar transacao_id direto, ou order_id, token, nsu
        transacao_id = dados.get('transacao_id') or dados.get('order_id') or dados.get('token') or dados.get('nsu', '')
        
        return {
            'transacao_id': transacao_id,
            'origem': 'WEB',
            'cliente_id': dados.get('cliente_id'),
            'cpf': dados.get('cpf', '').replace('.', '').replace('-', ''),
            'cliente_nome': dados.get('cliente_nome'),
            'valor': Decimal(str(dados.get('valor', 0))),
            'modalidade': ColetaDadosService.normalizar_modalidade(dados.get('modalidade', '')),
            'parcelas': int(dados.get('parcelas', 1)),
            'ip_address': dados.get('ip_address'),
            'device_fingerprint': dados.get('device_fingerprint'),
            'user_agent': dados.get('user_agent'),
            'bin_cartao': ColetaDadosService.extrair_bin_cartao(dados.get('numero_cartao')),
            'bandeira': dados.get('bandeira'),
            'loja_id': dados.get('loja_id'),
            'canal_id': dados.get('canal_id'),
            'terminal': None,
            'data_transacao': dados.get('data_transacao', datetime.now()),
        }
    
    @staticmethod
    def normalizar_dados(dados: Dict[str, Any], origem: Optional[str] = None) -> Dict[str, Any]:
        """
        Método unificado que detecta origem e normaliza automaticamente
        
        Args:
            dados: Dict com dados da transação
            origem: Origem explícita (POS, APP, WEB) - detecta automaticamente se None
        
        Returns:
            Dict normalizado para TransacaoRisco
        """
        # Detectar origem automaticamente se não informada
        if not origem:
            if 'nsu' in dados and 'terminal' in dados:
                origem = 'POS'
            elif 'device_fingerprint' in dados and 'user_agent' in dados:
                if 'mobile' in dados.get('user_agent', '').lower():
                    origem = 'APP'
                else:
                    origem = 'WEB'
            elif 'token' in dados:
                origem = 'WEB'
            else:
                # Fallback: tenta identificar pela estrutura
                origem = dados.get('origem', 'WEB')
        
        # Normalizar origem
        origem = ColetaDadosService.normalizar_origem(origem)
        
        # Chamar normalizador específico
        if origem == 'POS':
            return ColetaDadosService.normalizar_dados_pos(dados)
        elif origem == 'APP':
            return ColetaDadosService.normalizar_dados_app(dados)
        else:  # WEB
            return ColetaDadosService.normalizar_dados_web(dados)
    
    @staticmethod
    def validar_dados_minimos(dados: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Valida se dados mínimos necessários estão presentes
        
        Args:
            dados: Dict com dados normalizados
        
        Returns:
            Tupla (valido: bool, mensagem_erro: str ou None)
        """
        campos_obrigatorios = ['transacao_id', 'cpf', 'valor', 'modalidade']
        
        for campo in campos_obrigatorios:
            if not dados.get(campo):
                return False, f"Campo obrigatório ausente: {campo}"
        
        # Validar CPF (11 dígitos)
        cpf = dados.get('cpf', '')
        if not cpf.isdigit() or len(cpf) != 11:
            return False, f"CPF inválido: {cpf}"
        
        # Validar valor
        try:
            valor = Decimal(str(dados['valor']))
            if valor <= 0:
                return False, f"Valor inválido: {valor}"
        except:
            return False, f"Valor não é numérico: {dados['valor']}"
        
        return True, None
