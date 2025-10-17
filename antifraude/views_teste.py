"""
Views de Teste para Sistema Antifraude
Fase 2 - Semana 8: Validação de normalização de dados
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .services_coleta import ColetaDadosService


@api_view(['POST'])
def testar_normalizacao(request):
    """
    Endpoint de teste para validar normalização de dados
    
    POST /api/antifraude/teste/normalizar/
    
    Body: Dados de qualquer origem (POS, APP, WEB)
    
    Returns: Dados normalizados + validação
    """
    dados = request.data
    origem = dados.get('origem')
    
    try:
        # Normalizar
        dados_normalizados = ColetaDadosService.normalizar_dados(dados, origem)
        
        # Validar
        valido, erro = ColetaDadosService.validar_dados_minimos(dados_normalizados)
        
        return Response({
            'sucesso': True,
            'entrada': dados,
            'saida_normalizada': dados_normalizados,
            'validacao': {
                'valido': valido,
                'erro': erro
            },
            'detalhes': {
                'origem_detectada': dados_normalizados['origem'],
                'bin_extraido': dados_normalizados.get('bin_cartao'),
                'cpf_normalizado': dados_normalizados.get('cpf'),
                'modalidade_normalizada': dados_normalizados.get('modalidade')
            }
        })
    except Exception as e:
        return Response({
            'sucesso': False,
            'mensagem': f'Erro na normalização: {str(e)}',
            'entrada': dados
        }, status=400)


@api_view(['POST'])
def testar_extracao_bin(request):
    """
    Testa extração de BIN de diferentes formatos de cartão
    
    POST /api/antifraude/teste/bin/
    
    Body:
    {
        "numeros_cartao": [
            "4111111111111111",
            "4111 1111 1111 1111",
            "4111-1111-1111-1111",
            "5111111111111111"
        ]
    }
    """
    numeros = request.data.get('numeros_cartao', [])
    
    resultados = []
    for numero in numeros:
        bin_extraido = ColetaDadosService.extrair_bin_cartao(numero)
        resultados.append({
            'entrada': numero,
            'bin': bin_extraido,
            'valido': bin_extraido is not None and len(bin_extraido) == 6
        })
    
    return Response({
        'sucesso': True,
        'total_testado': len(numeros),
        'resultados': resultados
    })


@api_view(['GET'])
def exemplo_payloads(request):
    """
    Retorna exemplos de payloads para cada origem
    
    GET /api/antifraude/teste/exemplos/
    """
    return Response({
        'pos': {
            'descricao': 'Transação via Terminal POS',
            'payload': {
                'nsu': '148482386',
                'cpf': '12345678900',
                'cliente_id': 123,
                'cliente_nome': 'João Silva',
                'valor': 150.00,
                'modalidade': 'PIX',
                'parcelas': 1,
                'numero_cartao': '4111111111111111',
                'bandeira': 'VISA',
                'terminal': 'POS001',
                'loja_id': 1,
                'canal_id': 6
            }
        },
        'app': {
            'descricao': 'Transação via App Mobile',
            'payload': {
                'transaction_id': 'TXN-2025-001',
                'cpf': '12345678900',
                'cliente_id': 123,
                'cliente_nome': 'Maria Santos',
                'valor': 250.00,
                'modalidade': 'CREDITO',
                'parcelas': 3,
                'numero_cartao': '5111111111111111',
                'bandeira': 'MASTERCARD',
                'ip_address': '192.168.1.100',
                'device_fingerprint': 'abc123xyz',
                'user_agent': 'WallClub/1.0 (iPhone; iOS 15.0)',
                'loja_id': 1,
                'canal_id': 6
            }
        },
        'web': {
            'descricao': 'Transação via Checkout Web',
            'payload': {
                'order_id': 'ORD-2025-001',
                'token': 'tok_abc123',
                'cpf': '12345678900',
                'cliente_id': 123,
                'cliente_nome': 'Pedro Costa',
                'valor': 500.00,
                'modalidade': 'PARCELADO',
                'parcelas': 6,
                'numero_cartao': '4111 1111 1111 1111',
                'bandeira': 'VISA',
                'ip_address': '201.10.20.30',
                'device_fingerprint': 'web_fingerprint_123',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'loja_id': 1,
                'canal_id': 6
            }
        }
    })
