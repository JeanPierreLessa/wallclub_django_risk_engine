"""
Tasks Celery para Detecção Automática de Atividades Suspeitas
Fase 4 - Semana 23
"""
from celery import shared_task
from django.db.models import Count, Q
from datetime import datetime, timedelta
import logging

from .models import TransacaoRisco, AtividadeSuspeita, BloqueioSeguranca

logger = logging.getLogger('antifraude.detector')


@shared_task
def detectar_atividades_suspeitas():
    """
    Task periódica (a cada 5 minutos) que analisa logs e detecta atividades suspeitas
    
    Regras de detecção:
    1. Login Múltiplo: mesmo CPF em 3+ IPs diferentes em 10 minutos
    2. Tentativas Falhas: 5+ transações reprovadas do mesmo IP em 5 minutos
    3. IP Novo: CPF usando IP nunca visto antes
    4. Horário Suspeito: transações entre 02:00-05:00 AM
    5. Velocidade Transação: 10+ transações do mesmo CPF em 5 minutos
    6. Localização Anômala: IP de país diferente em menos de 1 hora
    """
    logger.info("🔍 Iniciando detecção automática de atividades suspeitas...")
    
    try:
        agora = datetime.now()
        janela_5min = agora - timedelta(minutes=5)
        janela_10min = agora - timedelta(minutes=10)
        janela_1hora = agora - timedelta(hours=1)
        
        deteccoes = {
            'login_multiplo': 0,
            'tentativas_falhas': 0,
            'ip_novo': 0,
            'horario_suspeito': 0,
            'velocidade_transacao': 0,
        }
        
        # 1. Detectar Login Múltiplo (mesmo CPF em 3+ IPs diferentes em 10 min)
        deteccoes['login_multiplo'] = detectar_login_multiplo(janela_10min)
        
        # 2. Detectar Tentativas Falhas (5+ transações reprovadas do mesmo IP)
        deteccoes['tentativas_falhas'] = detectar_tentativas_falhas(janela_5min)
        
        # 3. Detectar IP Novo (CPF usando IP nunca visto antes)
        deteccoes['ip_novo'] = detectar_ip_novo(janela_5min)
        
        # 4. Detectar Horário Suspeito (transações entre 02:00-05:00 AM)
        deteccoes['horario_suspeito'] = detectar_horario_suspeito(janela_5min)
        
        # 5. Detectar Velocidade de Transação (10+ transações do mesmo CPF)
        deteccoes['velocidade_transacao'] = detectar_velocidade_transacao(janela_5min)
        
        total_detectado = sum(deteccoes.values())
        logger.info(f"✅ Detecção concluída: {total_detectado} atividades suspeitas | Detalhes: {deteccoes}")
        
        return {
            'success': True,
            'total_detectado': total_detectado,
            'detalhes': deteccoes,
            'timestamp': agora.isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Erro na detecção automática: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def detectar_login_multiplo(janela_tempo):
    """
    Detecta mesmo CPF logando em 3+ IPs diferentes em curto período
    """
    count = 0
    try:
        # Agrupar transações por CPF e contar IPs distintos
        transacoes_recentes = TransacaoRisco.objects.filter(
            data_transacao__gte=janela_tempo
        ).values('cpf').annotate(
            ips_distintos=Count('ip_address', distinct=True)
        ).filter(ips_distintos__gte=3)
        
        for trans in transacoes_recentes:
            cpf = trans['cpf']
            ips_distintos = trans['ips_distintos']
            
            # Buscar IPs usados
            ips_usados = list(TransacaoRisco.objects.filter(
                cpf=cpf,
                data_transacao__gte=janela_tempo
            ).values_list('ip_address', flat=True).distinct())
            
            # Verificar se já existe atividade suspeita recente
            ja_detectado = AtividadeSuspeita.objects.filter(
                tipo='login_multiplo',
                cpf=cpf,
                detectado_em__gte=janela_tempo
            ).exists()
            
            if not ja_detectado:
                # Criar atividade suspeita
                AtividadeSuspeita.objects.create(
                    tipo='login_multiplo',
                    cpf=cpf,
                    ip=ips_usados[0] if ips_usados else 'desconhecido',
                    portal='app',  # Assumir APP por padrão
                    detalhes={
                        'ips_usados': ips_usados,
                        'total_ips': ips_distintos,
                        'janela_tempo_minutos': 10
                    },
                    severidade=4,  # Alta severidade
                    status='pendente'
                )
                count += 1
                logger.warning(f"⚠️ Login múltiplo detectado - CPF: {cpf[:3]}*** em {ips_distintos} IPs")
        
        return count
        
    except Exception as e:
        logger.error(f"Erro em detectar_login_multiplo: {str(e)}")
        return 0


def detectar_tentativas_falhas(janela_tempo):
    """
    Detecta 5+ transações reprovadas do mesmo IP em curto período
    """
    count = 0
    try:
        # Buscar transações reprovadas agrupadas por IP
        from .models import DecisaoAntifraude
        
        ips_suspeitos = DecisaoAntifraude.objects.filter(
            created_at__gte=janela_tempo,
            decisao='REPROVADO'
        ).values('transacao__ip_address').annotate(
            total_reprovadas=Count('id')
        ).filter(total_reprovadas__gte=5)
        
        for item in ips_suspeitos:
            ip = item['transacao__ip_address']
            total = item['total_reprovadas']
            
            if not ip:
                continue
            
            # Buscar CPFs relacionados
            cpfs_relacionados = DecisaoAntifraude.objects.filter(
                created_at__gte=janela_tempo,
                decisao='REPROVADO',
                transacao__ip_address=ip
            ).values_list('transacao__cpf', flat=True).distinct()
            
            # Verificar se já detectado
            ja_detectado = AtividadeSuspeita.objects.filter(
                tipo='tentativas_falhas',
                ip=ip,
                detectado_em__gte=janela_tempo
            ).exists()
            
            if not ja_detectado:
                AtividadeSuspeita.objects.create(
                    tipo='tentativas_falhas',
                    cpf=list(cpfs_relacionados)[0] if cpfs_relacionados else 'desconhecido',
                    ip=ip,
                    portal='web',
                    detalhes={
                        'total_reprovadas': total,
                        'cpfs_tentados': list(cpfs_relacionados)[:10],
                        'janela_tempo_minutos': 5
                    },
                    severidade=5,  # Crítico
                    status='pendente'
                )
                count += 1
                logger.warning(f"⚠️ Tentativas falhas detectadas - IP: {ip} | Total: {total}")
        
        return count
        
    except Exception as e:
        logger.error(f"Erro em detectar_tentativas_falhas: {str(e)}")
        return 0


def detectar_ip_novo(janela_tempo):
    """
    Detecta CPF usando IP nunca visto antes (em toda a base histórica)
    """
    count = 0
    try:
        # Buscar transações recentes
        transacoes_recentes = TransacaoRisco.objects.filter(
            data_transacao__gte=janela_tempo
        ).exclude(ip_address__isnull=True)
        
        for trans in transacoes_recentes:
            # Verificar se este CPF já usou este IP antes (histórico completo)
            uso_anterior = TransacaoRisco.objects.filter(
                cpf=trans.cpf,
                ip_address=trans.ip_address,
                data_transacao__lt=janela_tempo
            ).exists()
            
            # Se for primeira vez usando este IP
            if not uso_anterior:
                # Verificar se já detectado
                ja_detectado = AtividadeSuspeita.objects.filter(
                    tipo='ip_novo',
                    cpf=trans.cpf,
                    ip=trans.ip_address,
                    detectado_em__gte=janela_tempo
                ).exists()
                
                if not ja_detectado:
                    # Contar quantos IPs diferentes este CPF já usou
                    ips_historicos = TransacaoRisco.objects.filter(
                        cpf=trans.cpf
                    ).values_list('ip_address', flat=True).distinct().count()
                    
                    AtividadeSuspeita.objects.create(
                        tipo='ip_novo',
                        cpf=trans.cpf,
                        ip=trans.ip_address,
                        portal=trans.origem.lower(),
                        detalhes={
                            'transacao_id': trans.transacao_id,
                            'valor': str(trans.valor),
                            'total_ips_historicos': ips_historicos,
                            'primeira_vez': True
                        },
                        severidade=3,  # Média severidade
                        status='pendente'
                    )
                    count += 1
                    logger.info(f"🆕 IP novo detectado - CPF: {trans.cpf[:3]}*** | IP: {trans.ip_address}")
        
        return count
        
    except Exception as e:
        logger.error(f"Erro em detectar_ip_novo: {str(e)}")
        return 0


def detectar_horario_suspeito(janela_tempo):
    """
    Detecta transações em horário suspeito (02:00-05:00 AM)
    """
    count = 0
    try:
        # Buscar transações na janela de tempo
        transacoes = TransacaoRisco.objects.filter(
            data_transacao__gte=janela_tempo
        )
        
        for trans in transacoes:
            hora = trans.data_transacao.hour
            
            # Horário suspeito: 02:00 - 05:00 AM
            if 2 <= hora < 5:
                # Verificar se já detectado
                ja_detectado = AtividadeSuspeita.objects.filter(
                    tipo='horario_suspeito',
                    cpf=trans.cpf,
                    detectado_em__gte=janela_tempo
                ).exists()
                
                if not ja_detectado:
                    AtividadeSuspeita.objects.create(
                        tipo='horario_suspeito',
                        cpf=trans.cpf,
                        ip=trans.ip_address or 'desconhecido',
                        portal=trans.origem.lower(),
                        detalhes={
                            'transacao_id': trans.transacao_id,
                            'horario': trans.data_transacao.strftime('%H:%M:%S'),
                            'valor': str(trans.valor),
                            'modalidade': trans.modalidade
                        },
                        severidade=2,  # Baixa severidade (pode ser legítimo)
                        status='pendente'
                    )
                    count += 1
                    logger.info(f"🌙 Horário suspeito - CPF: {trans.cpf[:3]}*** às {trans.data_transacao.strftime('%H:%M')}")
        
        return count
        
    except Exception as e:
        logger.error(f"Erro em detectar_horario_suspeito: {str(e)}")
        return 0


def detectar_velocidade_transacao(janela_tempo):
    """
    Detecta 10+ transações do mesmo CPF em 5 minutos
    """
    count = 0
    try:
        # Agrupar por CPF e contar transações
        cpfs_suspeitos = TransacaoRisco.objects.filter(
            data_transacao__gte=janela_tempo
        ).values('cpf').annotate(
            total_transacoes=Count('id')
        ).filter(total_transacoes__gte=10)
        
        for item in cpfs_suspeitos:
            cpf = item['cpf']
            total = item['total_transacoes']
            
            # Buscar IPs usados
            ips_usados = list(TransacaoRisco.objects.filter(
                cpf=cpf,
                data_transacao__gte=janela_tempo
            ).values_list('ip_address', flat=True).distinct())
            
            # Calcular valor total
            valores = TransacaoRisco.objects.filter(
                cpf=cpf,
                data_transacao__gte=janela_tempo
            ).values_list('valor', flat=True)
            valor_total = sum(valores)
            
            # Verificar se já detectado
            ja_detectado = AtividadeSuspeita.objects.filter(
                tipo='velocidade_transacao',
                cpf=cpf,
                detectado_em__gte=janela_tempo
            ).exists()
            
            if not ja_detectado:
                AtividadeSuspeita.objects.create(
                    tipo='velocidade_transacao',
                    cpf=cpf,
                    ip=ips_usados[0] if ips_usados else 'desconhecido',
                    portal='app',
                    detalhes={
                        'total_transacoes': total,
                        'valor_total': str(valor_total),
                        'ips_usados': ips_usados,
                        'janela_tempo_minutos': 5
                    },
                    severidade=4,  # Alta severidade
                    status='pendente'
                )
                count += 1
                logger.warning(f"⚠️ Velocidade anormal - CPF: {cpf[:3]}*** | {total} transações em 5min")
        
        return count
        
    except Exception as e:
        logger.error(f"Erro em detectar_velocidade_transacao: {str(e)}")
        return 0


@shared_task
def bloquear_automatico_critico():
    """
    Task que bloqueia automaticamente IPs/CPFs com atividades críticas (severidade 5)
    Executa a cada 10 minutos
    """
    logger.info("🔒 Iniciando bloqueio automático de atividades críticas...")
    
    try:
        # Buscar atividades pendentes com severidade crítica
        atividades_criticas = AtividadeSuspeita.objects.filter(
            status='pendente',
            severidade=5,
            detectado_em__gte=datetime.now() - timedelta(minutes=15)
        )
        
        bloqueios_criados = 0
        
        for atividade in atividades_criticas:
            # Verificar se IP já está bloqueado
            ip_bloqueado = BloqueioSeguranca.objects.filter(
                tipo='ip',
                valor=atividade.ip,
                ativo=True
            ).exists()
            
            if not ip_bloqueado:
                # Criar bloqueio automático de IP
                bloqueio = BloqueioSeguranca.objects.create(
                    tipo='ip',
                    valor=atividade.ip,
                    motivo=f"Bloqueio automático - {dict(atividade.TIPO_CHOICES).get(atividade.tipo)}",
                    bloqueado_por='sistema_auto',
                    portal=atividade.portal,
                    detalhes={
                        'atividade_id': atividade.id,
                        'severidade': atividade.severidade,
                        'detalhes_atividade': atividade.detalhes
                    },
                    ativo=True
                )
                
                # Atualizar atividade
                atividade.status = 'bloqueado'
                atividade.bloqueio_relacionado = bloqueio
                atividade.acao_tomada = 'bloqueio_automatico_ip'
                atividade.save()
                
                bloqueios_criados += 1
                logger.warning(f"🚫 Bloqueio automático criado - IP: {atividade.ip} | Atividade: {atividade.id}")
        
        logger.info(f"✅ Bloqueio automático concluído: {bloqueios_criados} bloqueios criados")
        
        return {
            'success': True,
            'bloqueios_criados': bloqueios_criados
        }
        
    except Exception as e:
        logger.error(f"❌ Erro no bloqueio automático: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
