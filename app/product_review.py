"""Triagem de produtos; nao recomenda nem altera precos no ERP."""
from contextlib import closing
from datetime import date, datetime, timedelta
import calendar
from decimal import Decimal, InvalidOperation
import logging
import math
import os
import re
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

log = logging.getLogger(__name__)
IDENTIFIER = re.compile(r'^[a-z_][a-z0-9_]*$')
PERIOD_LABELS={'todos':'Todos os períodos','hoje':'Hoje','ontem':'Ontem','ate_hoje':'Até hoje',
 'semana':'Semana atual','semana_anterior':'Semana passada','mes_completo':'Mês atual','mes':'Início do mês até hoje',
 'mes_anterior':'Mês passado','7':'Últimos 7 dias','15':'Últimos 15 dias','30':'Últimos 30 dias','45':'Últimos 45 dias',
 '3meses':'Últimos 3 meses','6meses':'Últimos 6 meses','12meses':'Últimos 12 meses','intervalo':'Intervalo personalizado'}
PERIODS=set(PERIOD_LABELS)


def months_before(today,months):
    index=today.year*12+today.month-1-months
    year,month=divmod(index,12);month+=1
    return date(year,month,min(today.day,calendar.monthrange(year,month)[1]))


def interval(period, start=None, end=None, today=None):
    if period not in PERIODS:raise HTTPException(422,'Periodo invalido.')
    today=today or datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    if period=='todos':return None,None
    if period=='intervalo':
        if not start or not end or start>end:raise HTTPException(422,'Informe data inicial e final, em ordem cronologica.')
        if end==date.max:raise HTTPException(422,'Data final fora do intervalo permitido.')
        return start,end
    if period=='hoje':return today,today
    if period=='ontem':return today-timedelta(days=1),today-timedelta(days=1)
    if period=='ate_hoje':return None,today
    if period in {'7','15','30','45'}:return today-timedelta(days=int(period)-1),today
    if period in {'3meses','6meses','12meses'}:return months_before(today,int(period.split('meses')[0])),today
    if period in {'semana','semana_anterior'}:
        monday=today-timedelta(days=today.weekday()+(7 if period=='semana_anterior' else 0))
        return monday,monday+timedelta(days=6)
    if period=='mes':return today.replace(day=1),today
    if period=='mes_completo':return today.replace(day=1),today.replace(day=calendar.monthrange(today.year,today.month)[1])
    last=today.replace(day=1)-timedelta(days=1)
    return last.replace(day=1),last


def number(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def mark(row, minimum):
    row = dict(row)
    price, cost = number(row.get('preco')), number(row.get('custo'))
    margin = None
    if price is None or price <= 0:
        reason, label = 'preco_inconsistente', 'Conferir preco atual'
    elif cost is None or cost <= 0:
        reason, label = 'custo_inconsistente', 'Conferir custo'
    else:
        margin = (price-cost) / price * 100
        reason, label = ('margem_baixa', 'Margem abaixo do filtro') if margin < minimum else ('em_faixa', 'Dentro do filtro')
    row.update(margem_bruta=float(margin) if margin is not None else None,
               motivo_revisao=reason, motivo_descricao=label, revisar=reason != 'em_faixa')
    return row


def entry_config(prefix='A7_ENTRY_'):
    if os.getenv(prefix+'CONFIRMED', '') != '1':
        return None
    fields = {k: os.getenv(prefix+k, '').strip() for k in ['SCHEMA', 'TABLE', 'ID_COLUMN', 'UNIT_COLUMN', 'DATE_COLUMN', 'STATUS_COLUMN', 'STATUS_VALUE', 'ID_KIND']}
    for key in ['SCHEMA', 'TABLE', 'ID_COLUMN', 'UNIT_COLUMN', 'DATE_COLUMN', 'STATUS_COLUMN']:
        if not IDENTIFIER.fullmatch(fields[key]):
            raise HTTPException(422, 'Mapeamento da fonte de datas invalido. Consulte o guia de integracao.')
    if fields['ID_KIND'] not in {'produto', 'embalagem'} or not fields['STATUS_VALUE']:
        raise HTTPException(422, 'Informe identificador e status finalizado da fonte de entradas.')
    return fields


PURCHASE_CFOPS='1102,2102,3102,1403,2403,5101,5102,5401,5403,6101,6102,6401,6403,7101,7102'


def purchase_config():
    """Fonte fiscal dos CSVs; usuario confirmou C=concluida e A=adiciona estoque."""
    source=os.getenv('A7_PURCHASE_SOURCE','').strip()
    # Preserva fontes planas explicitamente configuradas em instalacoes existentes.
    if source not in {'','notafiscal'} or (not source and os.getenv('A7_PURCHASE_TABLE','').strip()):
        return entry_config('A7_PURCHASE_')
    if os.getenv('A7_PURCHASE_CONFIRMED','1').strip()=='0':
        return None
    schema=os.getenv('A7_PURCHASE_SCHEMA', 'public').strip() or 'public'
    status=os.getenv('A7_PURCHASE_STATUS_VALUE', '').strip() or 'C'
    movement=os.getenv('A7_PURCHASE_MOVEMENT_VALUE', '').strip() or 'A'
    cfops=[part.strip() for part in (os.getenv('A7_PURCHASE_CFOPS', '').strip() or PURCHASE_CFOPS).split(',') if part.strip()]
    if not IDENTIFIER.fullmatch(schema) or not status or not movement or not cfops or any(not re.fullmatch(r'\d{4}',part) for part in cfops):
        raise HTTPException(422,'Confirme esquema, status, movimento de entrada e CFOPs de compra da fonte fiscal.')
    return dict(SOURCE='notafiscal',SCHEMA=schema,STATUS_VALUE=status,MOVEMENT_VALUE=movement,CFOPS=cfops)


def check_purchase_columns(cursor, config):
    if config.get('SOURCE') != 'notafiscal':
        return check_entry_columns(cursor,config)
    required={
        'notafiscal':{'id','unidadenegocioid','fornecedorid','datahoraentrada','status','tipomovimentacaofisica'},
        'itemnotafiscal':{'notafiscalid','embalagemid','quantidade','bonificacao','itemsemmovimentacao','cfop'},
        'embalagem':{'id','produtoid'},
    }
    stamp_kind=None
    for table,needed in required.items():
        cursor.execute('SELECT column_name,data_type FROM information_schema.columns WHERE table_schema=%s AND table_name=%s',(config['SCHEMA'],table))
        columns=dict(cursor.fetchall())
        if not needed.issubset(columns):
            raise HTTPException(422,'Fonte fiscal de compras incompleta no Alpha7: '+table+'.')
        if table=='notafiscal':stamp_kind=columns['datahoraentrada']
        if table=='itemnotafiscal' and any(columns[name]!='boolean' for name in ('bonificacao','itemsemmovimentacao')):
            raise HTTPException(422,'Tipos dos indicadores de item fiscal precisam ser validados.')
    if stamp_kind not in {'date','timestamp without time zone','timestamp with time zone'}:
        raise HTTPException(422,'Data de entrada fiscal precisa ser data ou timestamp.')
    return stamp_kind


def check_entry_columns(cursor, config):
    cursor.execute('SELECT column_name,data_type FROM information_schema.columns WHERE table_schema=%s AND table_name=%s', (config['SCHEMA'], config['TABLE']))
    columns = dict(cursor.fetchall())
    required = {config[k] for k in ['ID_COLUMN', 'UNIT_COLUMN', 'DATE_COLUMN', 'STATUS_COLUMN']}
    if not required.issubset(columns):
        raise HTTPException(422, 'Fonte de datas nao validada: colunas ausentes no Alpha7.')
    kind = columns[config['DATE_COLUMN']]
    if kind not in {'date', 'timestamp without time zone', 'timestamp with time zone'}:
        raise HTTPException(422, 'A coluna configurada precisa ser data ou timestamp.')
    return kind


def build_query(legacy_sql, config, timestamp_kind, mode, q, start, end, minimum, only_review, stock_only, limit, offset, price_type='todos', product_status='todos', date_field='ultima_entrada'):
    if date_field not in {'ultima_entrada','ultima_compra'}:raise HTTPException(422,'Campo de data invalido.')
    # Reutiliza joins e filtros de unidade da consulta validada existente.
    base = legacy_sql.split(' WHERE (%s=')[0]
    params = []
    entry = 'NULL::timestamp'
    if config and config.get('SOURCE')=='notafiscal':
        schema='"'+config['SCHEMA']+'"'
        stamp='nf.datahoraentrada'
        if timestamp_kind=='timestamp with time zone':stamp+=" AT TIME ZONE 'America/Sao_Paulo'"
        placeholders=','.join(['%s']*len(config['CFOPS']))
        entry=f'''(SELECT MAX({stamp}) FROM {schema}.notafiscal nf
          JOIN {schema}.itemnotafiscal item ON item.notafiscalid=nf.id
          JOIN {schema}.embalagem comprada ON comprada.id=item.embalagemid
          WHERE comprada.produtoid=p.id AND nf.unidadenegocioid=%s AND nf.status=%s
          AND nf.tipomovimentacaofisica=%s AND nf.fornecedorid IS NOT NULL
          AND nf.datahoraentrada IS NOT NULL AND item.quantidade>0
          AND item.bonificacao=FALSE AND item.itemsemmovimentacao=FALSE
          AND item.cfop::text IN ({placeholders}))'''
        params.extend([int(os.getenv('A7_UNIT','1')),config['STATUS_VALUE'],config['MOVEMENT_VALUE'],*config['CFOPS']])
    elif config:
        quote = lambda name: '"' + name + '"'  # Identificadores validados por entry_config.
        stamp = 'src.' + quote(config['DATE_COLUMN'])
        if timestamp_kind == 'timestamp with time zone':
            stamp += " AT TIME ZONE 'America/Sao_Paulo'"
        target = 'p.id' if config['ID_KIND'] == 'produto' else 'e.id'
        entry = f'(SELECT MAX({stamp}) FROM {quote(config["SCHEMA"])}.{quote(config["TABLE"])} src WHERE src.{quote(config["ID_COLUMN"])}={target} AND src.{quote(config["UNIT_COLUMN"])}=%s AND src.{quote(config["STATUS_COLUMN"])}=%s)'
        params.extend([int(os.getenv('A7_UNIT', '1')), config['STATUS_VALUE']])
    base = base.replace(' FROM produto p JOIN', f', p.tipopreco AS tipo_preco, {entry} AS {date_field} FROM produto p JOIN', 1)
    params.extend([int(os.getenv('A7_UNIT', '1'))] * 4)
    expressions = {'ean': "COALESCE(e.codigobarras,'')", 'codigo': 'CAST(p.codigo AS TEXT)',
                   'produto': "concat_ws(' ',p.descricao,e.descricao,p.codigo::text,e.codigobarras)"}
    base += f' WHERE (%s=\'\' OR {expressions[mode]} ILIKE %s)'
    params.extend([q, '%'+q+'%'])
    if price_type!='todos':
        base+=' AND p.tipopreco=%s';params.append({'liberado':'L','monitorado':'M'}[price_type])
    if product_status!='todos':
        base+=' AND p.status=%s';params.append({'ativo':'A','inativo':'I'}[product_status])
    predicates = []
    if start:
        predicates.append(date_field+' >= %s');params.append(start)
    if end:
        predicates.append(date_field+' < %s');params.append(end+timedelta(days=1))
    if only_review:
        predicates.append("(preco IS NULL OR preco<=0 OR preco::text IN ('NaN','Infinity','-Infinity') OR custo IS NULL OR custo<=0 OR custo::text IN ('NaN','Infinity','-Infinity') OR ((preco-custo)/NULLIF(preco,0)*100)<%s)")
        params.append(minimum)
    if stock_only:
        predicates.append('estoque > 0')
    query = 'WITH candidatos AS (' + base + ') SELECT *,COUNT(*) OVER() AS total_filtrado FROM candidatos'
    if predicates:
        query += ' WHERE ' + ' AND '.join(predicates)
    query += f' ORDER BY {date_field} DESC NULLS LAST,descricao,embalagem_id LIMIT %s OFFSET %s'
    params.extend([limit+1, offset])
    return query, tuple(params)


def make_router(db_factory, demo_loader, legacy_sql, mode_getter):
    router = APIRouter(prefix='/api/revisao', tags=['Triagem de produtos'])

    @router.get('/opcoes')
    def options():
        config=entry_config();purchase=purchase_config()
        available=bool(config) if mode_getter()!='demo' else any(r.get('ultima_entrada') for r in demo_loader())
        purchase_available=bool(purchase) if mode_getter()!='demo' else any(r.get('ultima_compra') for r in demo_loader())
        today=datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        presets=[]
        for key,label in PERIOD_LABELS.items():
            first,last=interval(key,today=today) if key!='intervalo' else (None,None)
            presets.append({'id':key,'nome':label,'inicio':first,'fim':last})
        return {'ultima_compra_disponivel':purchase_available,'hoje':today,'intervalos':presets,
                'mensagem_compra':'Ultima compra disponivel.' if purchase_available else 'Ultima compra ainda sem mapeamento confirmado. O periodo de 45 dias nao pode ser aplicado. Selecione Todos os periodos para consultar sem datas ou gere o diagnostico no servidor.',
                'ultima_entrada_disponivel': available, 'origem_entrada': 'fonte Alpha7 configurada; validar no servidor' if config else None,
                'mensagem': 'Datas de entrada disponiveis.' if available else 'Data real da ultima entrada ainda nao mapeada no Alpha7. A data de custo nao sera usada como entrada.',
                'write_enabled': False, 'pricing_enabled': False}

    @router.get('/produtos')
    def review(q: str = Query('', max_length=120), modo: str = Query('produto', pattern='^(produto|ean|codigo)$'),
               periodo: str = 'todos', inicio: date | None = None, fim: date | None = None,
               tipo_preco:str=Query('liberado',pattern='^(liberado|monitorado|todos)$'),
               status_produto:str=Query('ativo',pattern='^(ativo|inativo|todos)$'),
               data_filtro:str=Query('entrada',pattern='^(entrada|compra)$'),
               margem_minima: float = Query(30, ge=0, le=90), somente_revisar: bool = True,
               somente_estoque: bool = False, limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
        start, end = interval(periodo, inicio, fim)
        date_field='ultima_compra' if data_filtro=='compra' else 'ultima_entrada'
        minimum = Decimal(str(margem_minima))
        q = q.strip()
        if mode_getter() == 'demo':
            rows = demo_loader()
            available = any(r.get(date_field) for r in rows)
            if (start or end) and not available:
                raise HTTPException(422,'Sem data real de '+('ultima compra' if data_filtro=='compra' else 'ultima entrada')+' nesta fonte; escolha Todos os periodos ou configure o mapeamento confirmado.')
            selected = []
            for row in rows:
                if tipo_preco!='todos' and row.get('tipo_preco',row.get('tipopreco'))!={'liberado':'L','monitorado':'M'}[tipo_preco]:continue
                if status_produto!='todos' and row.get('status')!={'ativo':'A','inativo':'I'}[status_produto]:continue
                text = str(row.get('ean') or '') if modo == 'ean' else str(row.get('codigo') or '') if modo == 'codigo' else ' '.join(str(row.get(k) or '') for k in ['descricao', 'codigo', 'ean', 'apresentacao'])
                if q.casefold() not in text.casefold():
                    continue
                stamp = str(row.get(date_field) or '')[:10]
                if (start or end) and (not stamp or (start and stamp<start.isoformat()) or (end and stamp>end.isoformat())):
                    continue
                item = mark(row, minimum)
                if somente_revisar and not item['revisar']:
                    continue
                if somente_estoque and (number(row.get('estoque')) or Decimal(0)) <= 0:
                    continue
                item.setdefault(date_field,None)
                selected.append(item)
            selected.sort(key=lambda r: (r.get('descricao', ''), str(r.get('embalagem_id', ''))))
            selected.sort(key=lambda r: str(r.get(date_field) or ''), reverse=True)
            total = len(selected)
            data = selected[offset:offset+limit]
            more = offset+limit < total
        elif mode_getter() == 'postgres':
            config = purchase_config() if data_filtro=='compra' else entry_config()
            if (start or end) and not config:
                raise HTTPException(422,'Ultima '+('compra' if data_filtro=='compra' else 'entrada')+' sem mapeamento confirmado. Selecione Todos os periodos ou execute o diagnostico de compras no servidor.')
            try:
                with closing(db_factory()) as con:
                    with con.cursor() as cursor:
                        kind = (check_purchase_columns(cursor,config) if data_filtro=='compra' else check_entry_columns(cursor,config)) if config else None
                        query, params = build_query(legacy_sql, config, kind, modo, q, start, end, minimum, somente_revisar, somente_estoque, limit, offset,tipo_preco,status_produto,date_field)
                        cursor.execute(query, params)
                        names = [desc[0] for desc in cursor.description]
                        rows = [dict(zip(names, row)) for row in cursor.fetchall()]
                more = len(rows) > limit
                total = int(rows[0]['total_filtrado']) if rows else (0 if offset == 0 else None)
                data = [mark(r, minimum) for r in rows[:limit]]
                for item in data:
                    item.pop('total_filtrado', None)
                    for key, value in list(item.items()):
                        if isinstance(value, Decimal):
                            item[key] = float(value) if value.is_finite() else None
                        elif isinstance(value, float) and not math.isfinite(value):
                            item[key] = None
            except HTTPException:
                raise
            except Exception as exc:
                log.exception('Falha na triagem de produtos Alpha7')
                raise HTTPException(503, 'Falha na consulta Alpha7. Confira mapeamento, permissoes e colunas; detalhes no log.') from exc
        else:
            raise HTTPException(400, 'MODE invalido')
        return {'items': data, 'total': total, 'has_more': more, 'offset': offset, 'limit': limit,
                'demo': mode_getter() == 'demo','tipo_preco':tipo_preco,'status_produto':status_produto,'data_filtro':data_filtro, 'periodo': {'inicio': start, 'fim': end},
                'criterio': 'Triagem por margem bruta e consistencia de custo/preco; nao e recomendacao automatica.',
                'write_enabled': False, 'pricing_enabled': False}

    return router
