"""Cadastro local de concorrentes descobertos; enriquecimento cadastral publico."""
from contextlib import closing,contextmanager
from datetime import datetime,timedelta,timezone
import json
import logging
import math
import re
import sqlite3
import threading
import time
import unicodedata
from urllib.request import Request as URLRequest,urlopen

from fastapi import APIRouter,Header,HTTPException,Query,Request
from pydantic import BaseModel,Field
from app.search_center import get_center,mutation

log=logging.getLogger(__name__)
cnpj_lock=threading.Lock()
last_cnpj=float('-inf')


def now():return datetime.now(timezone.utc).isoformat()


def normalize_cnpj(value):
    if not isinstance(value,str):return None
    value=re.sub(r'[.\s/\-]','',value.upper())
    if len(value)==16 and value.startswith('BR'):value=value[2:]
    if not re.fullmatch(r'[A-Z0-9]{12}[0-9]{2}',value) or len(set(value))==1:return None
    base=value[:12]
    for weights in [[5,4,3,2,9,8,7,6,5,4,3,2],[6,5,4,3,2,9,8,7,6,5,4,3,2]]:
        rem=sum((ord(char)-48)*weight for char,weight in zip(base,weights))%11
        base+=str(0 if rem<2 else 11-rem)
    return value if base==value else None


@contextmanager
def database(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path,timeout=10)) as con:
        con.row_factory=sqlite3.Row
        con.executescript('''
        CREATE TABLE IF NOT EXISTS concorrentes_cadastro(
          id INTEGER PRIMARY KEY,fonte_id TEXT UNIQUE NOT NULL,nome TEXT NOT NULL,
          grupo TEXT,grupo_confirmado INTEGER NOT NULL DEFAULT 0,latitude REAL NOT NULL,longitude REAL NOT NULL,
          endereco TEXT NOT NULL,site TEXT,cnpj TEXT,cnpj_origem TEXT,dados_cnpj TEXT,
          cnpj_status TEXT NOT NULL DEFAULT 'nao_identificado',cnpj_consultado_em TEXT,cnpj_tentado_em TEXT,
          criado_em TEXT NOT NULL,atualizado_em TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_concorrentes_lat ON concorrentes_cadastro(latitude);
        CREATE TABLE IF NOT EXISTS concorrentes_auditoria(
          id INTEGER PRIMARY KEY,concorrente_id INTEGER NOT NULL,acao TEXT NOT NULL,
          antes TEXT NOT NULL,depois TEXT NOT NULL,criado_em TEXT NOT NULL);
        ''')
        with con:yield con


def audit(con,identifier,action,before,after):
    con.execute('INSERT INTO concorrentes_auditoria(concorrente_id,acao,antes,depois,criado_em) VALUES(?,?,?,?,?)',
                (identifier,action,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),now()))


def register(path,rows,observed_at):
    added=updated=0
    with database(path) as con:
        for row in rows:
            if not re.fullmatch(r'(node|way|relation)/[1-9][0-9]*',str(row.get('fonte_id',''))):continue
            lat,lon=row.get('latitude'),row.get('longitude')
            if not isinstance(lat,(int,float)) or not isinstance(lon,(int,float)) or not(math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):continue
            old=con.execute('SELECT * FROM concorrentes_cadastro WHERE fonte_id=?',(row['fonte_id'],)).fetchone()
            values={key:row.get(key) for key in ['fonte_id','nome','grupo','latitude','longitude','endereco','site']}
            values['endereco']=values['endereco'] or ''
            values['grupo_confirmado']=int(bool(row.get('grupo_confirmado')))
            cnpj=normalize_cnpj(row.get('cnpj'))
            if old:
                before=dict(old)
                if old['grupo_confirmado'] and not values['grupo_confirmado']:
                    values.update(grupo=old['grupo'],grupo_confirmado=1)
                changed=any(old[key]!=value for key,value in values.items())
                if changed:
                    con.execute('UPDATE concorrentes_cadastro SET nome=?,grupo=?,grupo_confirmado=?,latitude=?,longitude=?,endereco=?,site=?,atualizado_em=? WHERE id=?',
                                (values['nome'],values['grupo'],values['grupo_confirmado'],lat,lon,values['endereco'],values['site'],observed_at,old['id']))
                    updated+=1
                    audit(con,old['id'],'atualizacao_fonte',before,values)
                if cnpj and not old['cnpj']:
                    con.execute("UPDATE concorrentes_cadastro SET cnpj=?,cnpj_origem='OSM - vinculo nao confirmado',cnpj_status='pendente' WHERE id=?",(cnpj,old['id']))
                    audit(con,old['id'],'cnpj_informado_na_fonte',{}, {'cnpj':cnpj})
            else:
                cur=con.execute('INSERT INTO concorrentes_cadastro(fonte_id,nome,grupo,grupo_confirmado,latitude,longitude,endereco,site,cnpj,cnpj_origem,cnpj_status,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                (values['fonte_id'],values['nome'],values['grupo'],values['grupo_confirmado'],lat,lon,values['endereco'],values['site'],cnpj,'OSM - vinculo nao confirmado' if cnpj else None,'pendente' if cnpj else 'nao_identificado',observed_at,observed_at))
                added+=1;audit(con,cur.lastrowid,'cadastro_automatico',{},values)
    identified=apply_identified(path)
    return {'adicionados':added,'atualizados':updated,'cnpjs_identificados':identified}


def normalized(value):
    return ' '.join(re.sub(r'[^A-Z0-9]+',' ',unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().upper()).split())


def identified_match(row,entry):
    # A revisao cobre estas filiais da regiao Americana/Santa Barbara, nao homonimos nacionais.
    if not (-22.78 <= row['latitude'] <= -22.73 and -47.39 <= row['longitude'] <= -47.33):return False
    if normalized(row['nome']) not in {normalized(name) for name in entry['nomes']}:return False
    if entry['fonte_id']:
        return row['fonte_id']==entry['fonte_id']
    address=normalized(row['endereco'])
    return (' '+entry['rua']+' ') in (' '+address+' ') and entry['numero'] in address.split()


def apply_identified(path):
    """Complementa filiais pesquisadas, sem rede e sem substituir CNPJ existente."""
    from app.identified_competitors import IDENTIFIED
    count=0
    with database(path) as con:
        rows=con.execute('SELECT * FROM concorrentes_cadastro WHERE cnpj IS NULL').fetchall()
        for row in rows:
            candidates=[entry for entry in IDENTIFIED if identified_match(row,entry)]
            if len(candidates)!=1:continue
            entry=candidates[0];data=entry['dados']
            if normalize_cnpj(entry['cnpj'])!=entry['cnpj'] or data.get('cnpj')!=entry['cnpj']:continue
            origin='Pesquisa de filial por endereco - '+entry['evidencia']
            cur=con.execute("UPDATE concorrentes_cadastro SET cnpj=?,cnpj_origem=?,dados_cnpj=?,cnpj_status='consultado_endereco_conferido',cnpj_consultado_em=? WHERE id=? AND cnpj IS NULL",
                (entry['cnpj'],origin,json.dumps(data,ensure_ascii=False),data['consultado_em'],row['id']))
            if cur.rowcount:
                count+=1
                audit(con,row['id'],'filial_identificada_por_endereco',{}, {'cnpj':entry['cnpj'],'evidencia':entry['evidencia'],'consultado_em':data['consultado_em']})
    return count


def set_group(path,source,group,reason='Conferido pelo operador'):
    # Uma transacao atualiza o cadastro e a regra aplicada nas proximas buscas.
    from app.local_stores import database as stores_database
    with stores_database(path):pass
    with database(path) as con:
        row=con.execute('SELECT * FROM concorrentes_cadastro WHERE fonte_id=?',(source,)).fetchone()
        if row is None:raise HTTPException(404,'Concorrente nao encontrado no cadastro. Recarregue a lista.')
        before=con.execute('SELECT * FROM lojas_grupos WHERE fonte_id=?',(source,)).fetchone()
        con.execute('INSERT INTO lojas_grupos VALUES(?,?,?,?) ON CONFLICT(fonte_id) DO UPDATE SET grupo=excluded.grupo,motivo=excluded.motivo,atualizado_em=excluded.atualizado_em',(source,group,reason,now()))
        con.execute('INSERT INTO lojas_auditoria(fonte_id,antes,depois,criado_em) VALUES(?,?,?,?)',(source,json.dumps(dict(before) if before else {}),json.dumps({'grupo':group,'motivo':reason}),now()))
        con.execute('UPDATE concorrentes_cadastro SET grupo=?,grupo_confirmado=1 WHERE id=?',(group,row['id']))
        audit(con,row['id'],'grupo_confirmado',{'grupo':row['grupo']},{'grupo':group,'motivo':reason})


def fetch_cnpj(cnpj):
    # BrasilAPI e um intermediario comunitario, nao uma API oficial da Receita.
    request=URLRequest('https://brasilapi.com.br/api/cnpj/v1/'+cnpj,headers={'User-Agent':'SonifarmaPrice/1.1.7 (+https://github.com/Sonifarma/SonifarmaPrice)'})
    with urlopen(request,timeout=12) as response:raw=response.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('Resposta cadastral excede limite.')
    data=json.loads(raw)
    if not isinstance(data,dict) or normalize_cnpj(data.get('cnpj'))!=cnpj:raise ValueError('CNPJ da resposta difere do consultado.')
    keys=['cnpj','razao_social','nome_fantasia','descricao_situacao_cadastral','data_situacao_cadastral',
          'cnae_fiscal','cnae_fiscal_descricao','descricao_tipo_de_logradouro','logradouro','numero','complemento','bairro','cep','municipio','uf','identificador_matriz_filial','descricao_identificador_matriz_filial']
    result={key:data.get(key) for key in keys}
    result.update(fonte='BrasilAPI - dados cadastrais de CNPJ; servico nao oficial',consultado_em=now(),url='https://brasilapi.com.br/api/cnpj/v1/'+cnpj,
                  aviso='Situacao cadastral nao comprova funcionamento. Endereco fiscal nao substitui o ponto da loja nem confirma o vinculo com a filial.')
    return result


def enrich(path,identifier,wait=False):
    global last_cnpj
    with database(path) as con:row=con.execute('SELECT * FROM concorrentes_cadastro WHERE id=?',(identifier,)).fetchone()
    if not row or not row['cnpj']:raise HTTPException(422,'CNPJ desta filial ainda nao identificado.')
    cnpj=row['cnpj']
    if row['dados_cnpj'] and row['cnpj_consultado_em'] and row['cnpj_consultado_em']>(datetime.now(timezone.utc)-timedelta(days=30)).isoformat():return
    if not cnpj_lock.acquire(blocking=False):raise HTTPException(429,'Consulta cadastral em andamento. Aguarde.')
    try:
        delay=1-(time.monotonic()-last_cnpj)
        if delay>0:
            if wait:time.sleep(delay)
            else:raise HTTPException(429,'Aguarde um segundo antes de nova consulta cadastral.')
        last_cnpj=time.monotonic()
        try:data=fetch_cnpj(cnpj)
        except Exception as exc:
            with database(path) as con:con.execute("UPDATE concorrentes_cadastro SET cnpj_status='falha_consulta',cnpj_tentado_em=? WHERE id=? AND cnpj=?",(now(),identifier,cnpj))
            log.warning('Fonte de cadastro CNPJ indisponivel para concorrente %s (%s)',identifier,type(exc).__name__)
            raise HTTPException(502,'Fonte cadastral indisponivel. Concorrente e dados anteriores preservados.') from exc
        with database(path) as con:
            current=con.execute('SELECT cnpj FROM concorrentes_cadastro WHERE id=?',(identifier,)).fetchone()
            if not current or current['cnpj']!=cnpj:raise HTTPException(409,'CNPJ alterado durante a consulta. Recarregue o cadastro.')
            con.execute("UPDATE concorrentes_cadastro SET dados_cnpj=?,cnpj_status='consultado_vinculo_pendente',cnpj_consultado_em=? WHERE id=?",(json.dumps(data,ensure_ascii=False),now(),identifier))
            audit(con,identifier,'consulta_cadastral',{}, {'cnpj':cnpj,'fonte':data['fonte']})
    finally:cnpj_lock.release()


def enrich_pending(path,sources):
    # Ate tres CNPJs explicitamente informados na fonte; nunca busca identidade por nome parecido.
    with database(path) as con:
        rows=con.execute("SELECT id,fonte_id FROM concorrentes_cadastro WHERE cnpj IS NOT NULL AND (dados_cnpj IS NULL OR cnpj_consultado_em < ?) AND (cnpj_status!='falha_consulta' OR cnpj_tentado_em < ?) ORDER BY id",
                         ((datetime.now(timezone.utc)-timedelta(days=30)).isoformat(),(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat())).fetchall()
    selected=[row['id'] for row in rows if row['fonte_id'] in sources][:3]
    for identifier in selected:
        try:enrich(path,identifier,wait=True)
        except HTTPException:pass


def within_radius(path,center,radius,distance):
    span=radius/110.0
    with database(path) as con:
        rows=con.execute('SELECT * FROM concorrentes_cadastro WHERE latitude BETWEEN ? AND ?', (max(-90,center['latitude']-span),min(90,center['latitude']+span))).fetchall()
    items=[]
    for row in rows:
        item=dict(row);dist=distance(center['latitude'],center['longitude'],item['latitude'],item['longitude'])
        if dist>radius:continue
        item['distancia_km']=round(dist,3)
        item['dados_cnpj']=json.loads(item['dados_cnpj']) if item['dados_cnpj'] else None
        item['fonte_url']=(('https://brasilapi.com.br/api/cnpj/v1/'+item['cnpj']) if item['cnpj'] else None) if item['fonte_id'].startswith('manual/') else 'https://www.openstreetmap.org/'+item['fonte_id']
        item['fonte']='Cadastro por CNPJ / operador' if item['fonte_id'].startswith('manual/') else 'OpenStreetMap'
        items.append(item)
    return sorted(items,key=lambda item:(item['distancia_km'],item['nome'],item['id']))


class LinkCnpj(BaseModel):
    cnpj:str=Field(min_length=14,max_length=30)


class ManualCompetitor(BaseModel):
    cnpj: str = Field(default='',max_length=30)
    nome: str = Field(min_length=2,max_length=200)
    endereco: str = Field(min_length=8,max_length=300)
    candidato_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    centro_versao: int = Field(ge=1)
    raio: float = Field(default=2,ge=0.5,le=50)
    grupo: str | None = None
    site: str = Field(default='',max_length=500)


def make_router(path,distance):
    router=APIRouter(prefix='/api/concorrentes',tags=['Cadastro automatico de concorrentes'])

    @router.get('')
    def listing(raio:float=Query(2,ge=0.5,le=50),centro_versao:int=Query(...,ge=1),q:str=Query('',max_length=120),limit:int=Query(100,ge=1,le=200),offset:int=Query(0,ge=0)):
        center=get_center(path())
        if center is None:raise HTTPException(422,'Cadastre o centro da pesquisa.')
        if center['versao']!=centro_versao:raise HTTPException(409,'Centro alterado. Recarregue o cadastro.')
        filled=apply_identified(path())
        rows=within_radius(path(),center,raio,distance)
        if q.strip():rows=[r for r in rows if q.casefold().strip() in ' '.join(str(r.get(k) or '') for k in ['nome','endereco','cnpj']).casefold()]
        return {'items':rows[offset:offset+limit],'total':len(rows),'has_more':offset+limit<len(rows),'centro':center,'raio_km':raio,'cnpjs_preenchidos':filled}

    @router.post('/cnpj/buscar')
    def lookup(body:LinkCnpj,request:Request,x_price_config:str|None=Header(default=None)):
        global last_cnpj
        mutation(request,x_price_config)
        cnpj=normalize_cnpj(body.cnpj)
        if not cnpj:raise HTTPException(422,'CNPJ invalido.')
        if not cnpj_lock.acquire(blocking=False):raise HTTPException(429,'Consulta em andamento. Aguarde.')
        try:
            if time.monotonic()-last_cnpj<1:raise HTTPException(429,'Aguarde um segundo antes de consultar novamente.')
            last_cnpj=time.monotonic()
            try:data=fetch_cnpj(cnpj)
            except Exception as exc:raise HTTPException(502,'Fonte cadastral indisponivel. Voce pode informar nome e endereco manualmente.') from exc
            address=' '.join(str(data.get(k) or '') for k in ['descricao_tipo_de_logradouro','logradouro','numero','complemento','bairro','municipio','uf','cep']).strip()
            return {'nome':data.get('nome_fantasia') or data.get('razao_social') or '', 'endereco':address,'dados_cnpj':data}
        finally:cnpj_lock.release()

    @router.post('/manual')
    def create(body:ManualCompetitor,request:Request,x_price_config:str|None=Header(default=None)):
        mutation(request,x_price_config)
        from app import search_center
        from app.local_stores import GROUPS,safe_site
        cnpj=normalize_cnpj(body.cnpj)
        if body.cnpj.strip() and not cnpj:raise HTTPException(422,'CNPJ invalido. Corrija ou deixe em branco para cadastrar sem CNPJ.')
        if not body.nome.strip() or len(body.endereco.strip())<8:raise HTTPException(422,'Informe nome e endereco da loja.')
        if body.grupo and body.grupo not in GROUPS:raise HTTPException(422,'Grupo invalido.')
        site=safe_site(body.site) if body.site.strip() else None
        if body.site.strip() and not site:raise HTTPException(422,'Site invalido. Informe URL com https://.')
        with search_center.database(path()) as con:
            center=con.execute('SELECT * FROM centro_pesquisa WHERE id=1').fetchone()
            if not center or center['versao']!=body.centro_versao:raise HTTPException(409,'Centro alterado ou pendente. Recarregue o cadastro.')
            candidate=con.execute('SELECT * FROM centro_candidatos WHERE id=?',(body.candidato_id,)).fetchone()
        if not candidate or candidate['criado_em']<(datetime.now(timezone.utc)-timedelta(days=1)).isoformat() or candidate['consulta']!=' '.join(body.endereco.split()).casefold():raise HTTPException(422,'Localizacao expirada ou endereco alterado. Busque o endereco novamente.')
        dist=distance(center['latitude'],center['longitude'],candidate['latitude'],candidate['longitude'])
        if dist>body.raio:raise HTTPException(422,'Localizacao fora do raio atual. Confira o endereco ou ajuste o raio da pesquisa.')
        with database(path()) as con:
            con.execute('BEGIN IMMEDIATE')
            existing=con.execute('SELECT id FROM concorrentes_cadastro WHERE cnpj=?',(cnpj,)).fetchone() if cnpj else None
            if not existing:
                existing=next((row for row in con.execute('SELECT id,nome,endereco FROM concorrentes_cadastro') if normalized(row['nome'])==normalized(body.nome) and normalized(row['endereco'])==normalized(body.endereco)),None)
            if existing:raise HTTPException(409,'Esta loja ou CNPJ ja esta cadastrado. Pesquise o cadastro existente.')
            timestamp=now()
            cur=con.execute("INSERT INTO concorrentes_cadastro(fonte_id,nome,grupo,grupo_confirmado,latitude,longitude,endereco,site,cnpj,cnpj_origem,cnpj_status,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('manual/pendente',body.nome.strip(),body.grupo,int(bool(body.grupo)),candidate['latitude'],candidate['longitude'],body.endereco.strip(),site,cnpj,'informado pelo operador - conferir filial' if cnpj else None,'pendente' if cnpj else 'nao_identificado',timestamp,timestamp))
            identifier=cur.lastrowid
            con.execute('UPDATE concorrentes_cadastro SET fonte_id=? WHERE id=?',('manual/'+str(identifier),identifier))
            audit(con,identifier,'cadastro_manual',{}, {'cnpj':cnpj,'nome':body.nome.strip(),'endereco':body.endereco.strip(),'latitude':candidate['latitude'],'longitude':candidate['longitude'],'grupo':body.grupo})
        return {'id':identifier,'distancia_km':round(dist,3),'mensagem':'Concorrente cadastrado e incluido na pesquisa dentro do raio.'}

    @router.post('/{identifier}/cnpj')
    def link(identifier:int,body:LinkCnpj,request:Request,x_price_config:str|None=Header(default=None)):
        mutation(request,x_price_config);cnpj=normalize_cnpj(body.cnpj)
        if not cnpj:raise HTTPException(422,'CNPJ invalido; confira identificador e digitos verificadores.')
        with database(path()) as con:
            row=con.execute('SELECT * FROM concorrentes_cadastro WHERE id=?',(identifier,)).fetchone()
            if row is None:raise HTTPException(404,'Concorrente nao encontrado.')
            if row['cnpj']!=cnpj:
                con.execute("UPDATE concorrentes_cadastro SET cnpj=?,cnpj_origem='informado pelo operador - conferir filial',dados_cnpj=NULL,cnpj_status='pendente',cnpj_consultado_em=NULL,cnpj_tentado_em=NULL WHERE id=?",(cnpj,identifier))
                audit(con,identifier,'cnpj_informado_operador',{'cnpj':row['cnpj']},{'cnpj':cnpj})
        enrich(path(),identifier)
        return {'mensagem':'Dados cadastrais consultados. Confira se o CNPJ corresponde a esta filial; o ponto da loja foi preservado.'}

    return router
