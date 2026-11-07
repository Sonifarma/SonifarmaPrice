"""Triagem de produtos; nao recomenda nem altera precos no ERP."""
from contextlib import closing
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import logging
import math
import os
import re
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

log = logging.getLogger(__name__)
IDENTIFIER = re.compile(r'^[a-z_][a-z0-9_]*$')
PERIODS = {'todos', 'hoje', 'ontem', '7', '15', '30', 'mes', 'mes_anterior', 'intervalo'}


def interval(period, start=None, end=None, today=None):
    if period not in PERIODS:
        raise HTTPException(422, 'Periodo invalido.')
    today = today or datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    if period == 'todos':
        return None, None
    if period == 'intervalo':
        if not start or not end or start > end:
            raise HTTPException(422, 'Informe data inicial e final, em ordem cronologica.')
        if end == date.max:
            raise HTTPException(422, 'Data final fora do intervalo permitido.')
        return start, end
    if period == 'hoje':
        return today, today
    if period == 'ontem':
        return today - timedelta(days=1), today - timedelta(days=1)
    if period in {'7', '15', '30'}:
        return today - timedelta(days=int(period)-1), today
    if period == 'mes':
        return today.replace(day=1), today
    end = today.replace(day=1) - timedelta(days=1)
    return end.replace(day=1), end


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


def entry_config():
    if os.getenv('A7_ENTRY_CONFIRMED', '') != '1':
        return None
    fields = {k: os.getenv('A7_ENTRY_'+k, '').strip() for k in ['SCHEMA', 'TABLE', 'ID_COLUMN', 'UNIT_COLUMN', 'DATE_COLUMN', 'STATUS_COLUMN', 'STATUS_VALUE', 'ID_KIND']}
    for key in ['SCHEMA', 'TABLE', 'ID_COLUMN', 'UNIT_COLUMN', 'DATE_COLUMN', 'STATUS_COLUMN']:
        if not IDENTIFIER.fullmatch(fields[key]):
            raise HTTPException(422, 'Mapeamento da ultima entrada invalido. Consulte o guia de integracao.')
    if fields['ID_KIND'] not in {'produto', 'embalagem'} or not fields['STATUS_VALUE']:
        raise HTTPException(422, 'Informe identificador e status finalizado da fonte de entradas.')
    return fields


def check_entry_columns(cursor, config):
    cursor.execute('SELECT column_name,data_type FROM information_schema.columns WHERE table_schema=%s AND table_name=%s', (config['SCHEMA'], config['TABLE']))
    columns = dict(cursor.fetchall())
    required = {config[k] for k in ['ID_COLUMN', 'UNIT_COLUMN', 'DATE_COLUMN', 'STATUS_COLUMN']}
    if not required.issubset(columns):
        raise HTTPException(422, 'Fonte de ultima entrada nao validada: colunas ausentes no Alpha7.')
    kind = columns[config['DATE_COLUMN']]
    if kind not in {'date', 'timestamp without time zone', 'timestamp with time zone'}:
        raise HTTPException(422, 'A coluna da ultima entrada precisa ser data ou timestamp.')
    return kind


def build_query(legacy_sql, config, timestamp_kind, mode, q, start, end, minimum, only_review, stock_only, limit, offset):
    # Reutiliza joins e filtros de unidade da consulta validada existente.
    base = legacy_sql.split(' WHERE (%s=')[0]
    params = []
    entry = 'NULL::timestamp'
    if config:
        quote = lambda name: '"' + name + '"'  # Identificadores validados por entry_config.
        stamp = 'src.' + quote(config['DATE_COLUMN'])
        if timestamp_kind == 'timestamp with time zone':
            stamp += " AT TIME ZONE 'America/Sao_Paulo'"
        target = 'p.id' if config['ID_KIND'] == 'produto' else 'e.id'
        entry = f'(SELECT MAX({stamp}) FROM {quote(config["SCHEMA"])}.{quote(config["TABLE"])} src WHERE src.{quote(config["ID_COLUMN"])}={target} AND src.{quote(config["UNIT_COLUMN"])}=%s AND src.{quote(config["STATUS_COLUMN"])}=%s)'
        params.extend([int(os.getenv('A7_UNIT', '1')), config['STATUS_VALUE']])
    base = base.replace(' FROM produto p JOIN', f', {entry} AS ultima_entrada FROM produto p JOIN', 1)
    params.extend([int(os.getenv('A7_UNIT', '1'))] * 4)
    expressions = {'ean': "COALESCE(e.codigobarras,'')", 'codigo': 'CAST(p.codigo AS TEXT)',
                   'produto': "concat_ws(' ',p.descricao,e.descricao,p.codigo::text,e.codigobarras)"}
    base += f' WHERE (%s=\'\' OR {expressions[mode]} ILIKE %s)'
    params.extend([q, '%'+q+'%'])
    predicates = []
    if start:
        predicates.append('ultima_entrada >= %s AND ultima_entrada < %s')
        params.extend([start, end + timedelta(days=1)])
    if only_review:
        predicates.append("(preco IS NULL OR preco<=0 OR preco::text IN ('NaN','Infinity','-Infinity') OR custo IS NULL OR custo<=0 OR custo::text IN ('NaN','Infinity','-Infinity') OR ((preco-custo)/NULLIF(preco,0)*100)<%s)")
        params.append(minimum)
    if stock_only:
        predicates.append('estoque > 0')
    query = 'WITH candidatos AS (' + base + ') SELECT *,COUNT(*) OVER() AS total_filtrado FROM candidatos'
    if predicates:
        query += ' WHERE ' + ' AND '.join(predicates)
    query += ' ORDER BY ultima_entrada DESC NULLS LAST,descricao,embalagem_id LIMIT %s OFFSET %s'
    params.extend([limit+1, offset])
    return query, tuple(params)


def make_router(db_factory, demo_loader, legacy_sql, mode_getter):
    router = APIRouter(prefix='/api/revisao', tags=['Triagem de produtos'])

    @router.get('/opcoes')
    def options():
        config = entry_config()
        available = bool(config) if mode_getter() != 'demo' else any(r.get('ultima_entrada') for r in demo_loader())
        return {'ultima_entrada_disponivel': available, 'origem_entrada': 'fonte Alpha7 configurada; validar no servidor' if config else None,
                'mensagem': 'Datas de entrada disponiveis.' if available else 'Data real da ultima entrada ainda nao mapeada no Alpha7. A data de custo nao sera usada como entrada.',
                'write_enabled': False, 'pricing_enabled': False}

    @router.get('/produtos')
    def review(q: str = Query('', max_length=120), modo: str = Query('produto', pattern='^(produto|ean|codigo)$'),
               periodo: str = 'todos', inicio: date | None = None, fim: date | None = None,
               margem_minima: float = Query(30, ge=0, le=90), somente_revisar: bool = True,
               somente_estoque: bool = False, limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
        start, end = interval(periodo, inicio, fim)
        minimum = Decimal(str(margem_minima))
        q = q.strip()
        if mode_getter() == 'demo':
            rows = demo_loader()
            available = any(r.get('ultima_entrada') for r in rows)
            if start and not available:
                raise HTTPException(422, 'Sem data real da ultima entrada nesta fonte; escolha Todos os periodos.')
            selected = []
            for row in rows:
                text = str(row.get('ean') or '') if modo == 'ean' else str(row.get('codigo') or '') if modo == 'codigo' else ' '.join(str(row.get(k) or '') for k in ['descricao', 'codigo', 'ean', 'apresentacao'])
                if q.casefold() not in text.casefold():
                    continue
                stamp = str(row.get('ultima_entrada') or '')[:10]
                if start and not (start.isoformat() <= stamp <= end.isoformat()):
                    continue
                item = mark(row, minimum)
                if somente_revisar and not item['revisar']:
                    continue
                if somente_estoque and (number(row.get('estoque')) or Decimal(0)) <= 0:
                    continue
                item.setdefault('ultima_entrada', None)
                selected.append(item)
            selected.sort(key=lambda r: (r.get('descricao', ''), str(r.get('embalagem_id', ''))))
            selected.sort(key=lambda r: str(r.get('ultima_entrada') or ''), reverse=True)
            total = len(selected)
            data = selected[offset:offset+limit]
            more = offset+limit < total
        elif mode_getter() == 'postgres':
            config = entry_config()
            if start and not config:
                raise HTTPException(422, 'Mapeie a fonte de ultima entrada antes de filtrar por datas. Consulte /api/diagnostic e o guia.')
            try:
                with closing(db_factory()) as con:
                    with con.cursor() as cursor:
                        kind = check_entry_columns(cursor, config) if config else None
                        query, params = build_query(legacy_sql, config, kind, modo, q, start, end, minimum, somente_revisar, somente_estoque, limit, offset)
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
                'demo': mode_getter() == 'demo', 'periodo': {'inicio': start, 'fim': end},
                'criterio': 'Triagem por margem bruta e consistencia de custo/preco; nao e recomendacao automatica.',
                'write_enabled': False, 'pricing_enabled': False}

    return router
