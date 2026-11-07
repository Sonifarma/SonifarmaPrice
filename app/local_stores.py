"""Descobre cadastros e sites declarados de lojas; nao coleta precos dos sites."""
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import logging
import math
import re
import sqlite3
import threading
import time
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request as URLRequest, urlopen

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from pydantic import BaseModel, Field
from app.search_center import get_center, mutation

log=logging.getLogger(__name__)
lock=threading.Lock()
last_search=float('-inf')
GROUPS={'supermercados','perfumarias','farmacias_redes','farmacias_independentes'}
ENDPOINT='https://overpass-api.de/api/interpreter'


class StoreSearch(BaseModel):
    raio: float=Field(default=2,ge=0.5,le=50)
    centro_versao: int=Field(ge=1)


class StoreGroup(BaseModel):
    grupo: str
    motivo: str=Field(min_length=3,max_length=300)


@contextmanager
def database(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path,timeout=10)) as con:
        con.row_factory=sqlite3.Row
        con.executescript('''
        CREATE TABLE IF NOT EXISTS lojas_buscas(id INTEGER PRIMARY KEY,criado_em TEXT NOT NULL,centro_versao INTEGER NOT NULL,raio REAL NOT NULL,estado TEXT NOT NULL,resultado TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS lojas_grupos(fonte_id TEXT PRIMARY KEY,grupo TEXT NOT NULL,motivo TEXT NOT NULL,atualizado_em TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS lojas_auditoria(id INTEGER PRIMARY KEY,fonte_id TEXT NOT NULL,antes TEXT NOT NULL,depois TEXT NOT NULL,criado_em TEXT NOT NULL);
        ''')
        with con:yield con


def now():return datetime.now(timezone.utc).isoformat()


def safe_site(value):
    if not isinstance(value,str) or not value or len(value)>2048 or any(c.isspace() or ord(c)<32 for c in value):return None
    if '\\' in value:return None
    if '://' not in value:value='https://'+value
    try:
        parts=urlsplit(value)
        if parts.scheme not in {'http','https'} or parts.username or parts.password:return None
        host=(parts.hostname or '').encode('idna').decode('ascii').lower()
        if not host or host.endswith(('.local','.localhost','.internal')):return None
        try:
            if not ipaddress.ip_address(host).is_global:return None
        except ValueError:
            if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',host):return None
        if parts.port not in {None,80,443}:return None
        return urlunsplit((parts.scheme,parts.netloc,parts.path or '/',parts.query,''))
    except (ValueError,UnicodeError):return None


def overpass(center,radius):
    around=f'around:{int(radius*1000)},{center["latitude"]},{center["longitude"]}'
    query=('[out:json][timeout:20][maxsize:8388608];('
           f'nwr["shop"~"^(supermarket|wholesale|cosmetics|perfumery)$"]({around});'
           f'nwr["amenity"="pharmacy"]({around}););out center tags 2001;')
    request=URLRequest(ENDPOINT,data=urlencode({'data':query}).encode(),headers={
        'User-Agent':'SonifarmaPrice/1.1.5 (https://github.com/Sonifarma/SonifarmaPrice)',
        'Content-Type':'application/x-www-form-urlencoded'})
    with urlopen(request,timeout=30) as response:raw=response.read(5_000_001)
    if len(raw)>5_000_000:raise ValueError('Resposta excede 5 MB; reduza o raio.')
    data=json.loads(raw)
    if data.get('remark') or not isinstance(data.get('elements'),list):raise ValueError('Resposta incompleta da fonte.')
    if len(data['elements'])>2000:raise ValueError('Mais de 2000 cadastros; reduza o raio.')
    return data['elements']


def normalize(elements,center,radius,distance,corrections):
    stores={}
    for element in elements:
        if not isinstance(element,dict):continue
        tags=element.get('tags') or {};point=element.get('center') or element
        if not isinstance(tags,dict) or not isinstance(point,dict):continue
        if tags.get('shop') not in {'supermarket','wholesale','cosmetics','perfumery'} and tags.get('amenity')!='pharmacy':continue
        try:
            lat,lon=float(point['lat']),float(point['lon'])
            if not(math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):continue
            dist=distance(center['latitude'],center['longitude'],lat,lon)
            if dist>radius or not tags.get('name') or element.get('type') not in {'node','way','relation'}:continue
            identifier=int(element['id'])
            if identifier<=0:continue
            source=element['type']+'/'+str(identifier)
        except (ValueError,TypeError,KeyError,OverflowError):continue
        group='supermercados' if tags.get('shop') in {'supermarket','wholesale'} else 'perfumarias' if tags.get('shop') in {'cosmetics','perfumery'} else None
        if source in corrections:group=corrections[source]
        site=safe_site(tags.get('website')) or safe_site(tags.get('contact:website'))
        from app.competitors import normalize_cnpj
        cnpj=next((value for key in ['ref:vatin','cnpj','taxid'] if (value:=normalize_cnpj(tags.get(key)))),None)
        stores[source]={'cnpj':cnpj,'fonte_id':source,'nome':str(tags['name'])[:200],'grupo':group,
          'grupo_confirmado':source in corrections,'revisao_necessaria':group is None,
          'distancia_km':round(dist,3),'site':site,'site_status':'declarado no cadastro OSM; nao verificado' if site else 'site nao informado ou invalido',
          'fonte_url':'https://www.openstreetmap.org/'+source,'fonte':'OpenStreetMap / Overpass',
          'latitude':lat,'longitude':lon,
          'endereco':' '.join(str(tags.get(k) or '') for k in ['addr:street','addr:housenumber','addr:city']).strip(),
          'aviso':'Cadastro de loja no raio; site pode ser da rede. Produto, estoque e preco local nao confirmados.'}
    return sorted(stores.values(),key=lambda row:(row['distancia_km'],row['fonte_id']))


def make_router(path,distance):
    router=APIRouter(prefix='/api/mercado/lojas',tags=['Lojas e sites no raio'])

    @router.post('/buscar')
    def search(body:StoreSearch,request:Request,background_tasks:BackgroundTasks,x_price_config:str|None=Header(default=None)):
        global last_search
        mutation(request,x_price_config)
        center=get_center(path())
        if center is None:raise HTTPException(422,'Cadastre o centro da pesquisa antes de buscar lojas.')
        if center['versao']!=body.centro_versao:raise HTTPException(409,'Centro alterado. Recarregue o cadastro.')
        cutoff=(datetime.now(timezone.utc)-timedelta(minutes=10)).isoformat()
        with database(path()) as con:
            corrections={r['fonte_id']:r['grupo'] for r in con.execute('SELECT * FROM lojas_grupos')}
            cached=con.execute("SELECT * FROM lojas_buscas WHERE centro_versao=? AND raio=? AND estado='concluido' AND criado_em>=? ORDER BY id DESC LIMIT 1",(body.centro_versao,body.raio,cutoff)).fetchone()
        if cached:
            result=json.loads(cached['resultado'])
            for row in result['lojas']:
                if row['fonte_id'] in corrections:row.update(grupo=corrections[row['fonte_id']],grupo_confirmado=True,revisao_necessaria=False)
            from app.competitors import register,enrich_pending
            stats=register(path(),result['lojas'],result['consultado_em'])
            background_tasks.add_task(enrich_pending,path(),{row['fonte_id'] for row in result['lojas']})
            return dict(result,cache=True,cadastro=stats)
        if not lock.acquire(blocking=False):raise HTTPException(429,'Busca de lojas em andamento. Aguarde.',headers={'Retry-After':'60'})
        try:
            if time.monotonic()-last_search<60:raise HTTPException(429,'Aguarde um minuto antes de outra busca online.',headers={'Retry-After':'60'})
            last_search=time.monotonic()
            try:
                rows=normalize(overpass(center,body.raio),center,body.raio,distance,corrections)
            except Exception as exc:
                log.exception('Falha na fonte de lojas no raio')
                with database(path()) as con:
                    con.execute('INSERT INTO lojas_buscas(criado_em,centro_versao,raio,estado,resultado) VALUES(?,?,?,?,?)',(now(),center['versao'],body.raio,'falha',json.dumps({'mensagem':'Fonte indisponivel ou resposta incompleta.'})))
                raise HTTPException(502,'Fonte de lojas indisponivel ou incompleta. Tente mais tarde ou reduza o raio.') from exc
            result={'lojas':rows,'centro':center,'raio_km':body.raio,'consultado_em':now(),'cache':False,
                    'aviso':'Sites declarados no OpenStreetMap. Nao comprova funcionamento, produto, estoque ou preco da filial. © colaboradores OSM (ODbL).'}
            with database(path()) as con:
                con.execute('INSERT INTO lojas_buscas(criado_em,centro_versao,raio,estado,resultado) VALUES(?,?,?,?,?)',(result['consultado_em'],center['versao'],body.raio,'concluido',json.dumps(result)))
            from app.competitors import register,enrich_pending
            result['cadastro']=register(path(),rows,result['consultado_em'])
            background_tasks.add_task(enrich_pending,path(),{row['fonte_id'] for row in rows})
            return result
        finally:lock.release()

    @router.put('/{tipo}/{identificador}/grupo')
    def group(tipo:str,identificador:int,body:StoreGroup,request:Request,x_price_config:str|None=Header(default=None)):
        mutation(request,x_price_config)
        if tipo not in {'node','way','relation'} or identificador<=0 or body.grupo not in GROUPS or len(body.motivo.strip())<3:raise HTTPException(422,'Grupo ou identificador invalido.')
        key=f'{tipo}/{identificador}'
        with database(path()) as con:
            before=con.execute('SELECT * FROM lojas_grupos WHERE fonte_id=?',(key,)).fetchone()
            con.execute('INSERT INTO lojas_grupos VALUES(?,?,?,?) ON CONFLICT(fonte_id) DO UPDATE SET grupo=excluded.grupo,motivo=excluded.motivo,atualizado_em=excluded.atualizado_em',(key,body.grupo,body.motivo,now()))
            con.execute('INSERT INTO lojas_auditoria(fonte_id,antes,depois,criado_em) VALUES(?,?,?,?)',(key,json.dumps(dict(before) if before else {}),json.dumps({'grupo':body.grupo,'motivo':body.motivo}),now()))
        from app.competitors import set_group
        set_group(path(),key,body.grupo)
        return {'fonte_id':key,'grupo':body.grupo}

    return router
