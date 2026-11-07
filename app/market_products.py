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


def make_detail_router(db_factory, demo_loader, mode_getter):
    router = APIRouter(prefix='/api/mercado/produtos', tags=['Ficha de produto'])

    @router.get('/{embalagem_id}')
    def detail(embalagem_id: int):
        if embalagem_id<=0:
            raise HTTPException(422,'Embalagem invalida.')
        if mode_getter()=='demo':
            row=next((dict(r) for r in demo_loader() if str(r.get('embalagem_id'))==str(embalagem_id)),None)
            if row is None:
                raise HTTPException(404,'Produto nao encontrado.')
            return {'produto':{k:row.get(k) for k in ['produto_id','embalagem_id','descricao','ean','codigo','apresentacao','preco']},
                    'classificacoes':row.get('classificacoes',[]),'grupo_remarcacao':row.get('grupo_remarcacao'),
                    'classificacao_disponivel':'classificacoes' in row,'grupo_remarcacao_disponivel':'grupo_remarcacao' in row,
                    'demo':True}
        if mode_getter()!='postgres':
            raise HTTPException(400,'MODE invalido')
        try:
            with closing(db_factory()) as con:
                with con.cursor() as cur:
                    cur.execute('SELECT table_name,column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=ANY(%s)',
                                (['classificacao','classificacaoproduto','gruporemarcacao','embalagem'],))
                    columns=set(cur.fetchall())
                    def has(table,*names):
                        return all((table,name) in columns for name in names)
                    def label(table):
                        return next((name for name in ['nome','descricao','denominacao'] if (table,name) in columns),None)
                    cur.execute('SELECT p.id AS produto_id,e.id AS embalagem_id,p.descricao,e.codigobarras AS ean,p.codigo,e.descricao AS apresentacao,e.precovenda AS preco FROM produto p JOIN embalagem e ON e.produtoid=p.id WHERE e.id=%s',(embalagem_id,))
                    row=cur.fetchone()
                    if row is None:
                        raise HTTPException(404,'Produto nao encontrado.')
                    product=dict(zip([d[0] for d in cur.description],row))
                    from decimal import Decimal
                    import math
                    price=product.get('preco')
                    if isinstance(price,Decimal):
                        product['preco']=float(price) if price.is_finite() else None
                    elif isinstance(price,float) and not math.isfinite(price):
                        product['preco']=None
                    cls_label,group_label=label('classificacao'),label('gruporemarcacao')
                    cls_available=bool(cls_label and has('classificacao','id') and has('classificacaoproduto','produtoid','classificacaoid'))
                    group_available=bool(group_label and has('gruporemarcacao','id') and has('embalagem','gruporemarcacaoid'))
                    classes=[];group=None;limited=False
                    if cls_available:
                        cur.execute(f'SELECT DISTINCT c.id,c."{cls_label}"::text FROM classificacaoproduto cp JOIN classificacao c ON c.id=cp.classificacaoid WHERE cp.produtoid=%s ORDER BY 2,1 LIMIT 101',(product['produto_id'],))
                        rows=cur.fetchall();limited=len(rows)>100
                        classes=[{'id':r[0],'nome':r[1]} for r in rows[:100]]
                    if group_available:
                        cur.execute(f'SELECT g.id,g."{group_label}"::text FROM embalagem e JOIN gruporemarcacao g ON g.id=e.gruporemarcacaoid WHERE e.id=%s',(embalagem_id,))
                        row=cur.fetchone()
                        if row:group={'id':row[0],'nome':row[1]}
            return {'produto':product,'classificacoes':classes,'grupo_remarcacao':group,
                    'classificacao_disponivel':cls_available,'grupo_remarcacao_disponivel':group_available,
                    'classificacoes_limitadas':limited,'demo':False}
        except HTTPException:
            raise
        except Exception as exc:
            log.exception('Falha na ficha de produto Alpha7')
            raise HTTPException(503,'Nao foi possivel consultar a ficha no Alpha7.') from exc

    return router
