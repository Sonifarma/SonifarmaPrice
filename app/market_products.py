"""Busca de identidade do produto; comparacao de precos permanece por EAN."""
from contextlib import closing
from fastapi import APIRouter, HTTPException, Query
import logging

log = logging.getLogger(__name__)


def lookup_query(q, limit, offset):
    # %, _ e barra digitados sao texto literal, nao curingas extras.
    text = '%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
    sql = """SELECT p.id AS produto_id,e.id AS embalagem_id,p.descricao,
      e.codigobarras AS ean,e.descricao AS apresentacao
      FROM produto p JOIN embalagem e ON e.produtoid=p.id
      WHERE p.descricao ILIKE %s ESCAPE '\\' OR e.codigobarras=%s
      ORDER BY p.descricao,e.id LIMIT %s OFFSET %s"""
    return sql, (text, q, limit+1, offset)


def make_router(db_factory, demo_loader, mode_getter):
    router = APIRouter(prefix='/api/mercado', tags=['Pesquisa de produtos'])

    @router.get('/produtos')
    def lookup(q: str = Query(..., min_length=2, max_length=120),
               limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0)):
        q = q.strip()
        if len(q) < 2:
            raise HTTPException(422, 'Digite ao menos dois caracteres do produto ou o EAN.')
        if mode_getter() == 'demo':
            rows = [dict(r) for r in demo_loader() if q.casefold() in str(r.get('descricao') or '').casefold() or q == str(r.get('ean') or '')]
            rows.sort(key=lambda r: (r.get('descricao') or '', str(r.get('embalagem_id') or '')))
            rows = rows[offset:offset+limit+1]
        elif mode_getter() == 'postgres':
            try:
                with closing(db_factory()) as con:
                    with con.cursor() as cursor:
                        sql, params = lookup_query(q, limit, offset)
                        cursor.execute(sql, params)
                        names = [desc[0] for desc in cursor.description]
                        rows = [dict(zip(names, row)) for row in cursor.fetchall()]
            except Exception as exc:
                log.exception('Falha ao buscar identidade do produto Alpha7')
                raise HTTPException(503, 'Nao foi possivel buscar produtos no Alpha7. Tente novamente.') from exc
        else:
            raise HTTPException(400, 'MODE invalido')
        keys = ['produto_id', 'embalagem_id', 'descricao', 'ean', 'apresentacao']
        return {'items': [{key:r.get(key) for key in keys} for r in rows[:limit]],
                'has_more': len(rows)>limit, 'offset': offset, 'limit': limit,
                'demo': mode_getter() == 'demo'}

    return router
