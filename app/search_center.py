"""Centro geografico cadastrado localmente a partir de endereco confirmado."""
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
import json
import logging
import math
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
lock = threading.Lock()
last_lookup = float('-inf')


class AddressSearch(BaseModel):
    endereco: str = Field(min_length=8, max_length=300)


class CenterSave(BaseModel):
    candidato_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    versao: int = Field(default=0, ge=0)


@contextmanager
def database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=10)) as con:
        con.row_factory = sqlite3.Row
        con.executescript('''
        CREATE TABLE IF NOT EXISTS centro_candidatos (
          id TEXT PRIMARY KEY, consulta TEXT NOT NULL, endereco TEXT NOT NULL,
          latitude REAL NOT NULL, longitude REAL NOT NULL, tipo TEXT NOT NULL,
          criado_em TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_centro_consulta ON centro_candidatos(consulta);
        CREATE TABLE IF NOT EXISTS centro_pesquisa (
          id INTEGER PRIMARY KEY CHECK(id=1), endereco TEXT NOT NULL,
          latitude REAL NOT NULL, longitude REAL NOT NULL, versao INTEGER NOT NULL,
          atualizado_em TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS centro_auditoria (
          id INTEGER PRIMARY KEY, antes TEXT NOT NULL, depois TEXT NOT NULL,
          criado_em TEXT NOT NULL);
        ''')
        with con:
            yield con


def now():
    return datetime.now(timezone.utc).isoformat()


def public_center(row):
    if row is None:
        return None
    data = dict(row)
    data.pop('id', None)
    lat, lon = data['latitude'], data['longitude']
    data['mapa_url'] = f'https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}'
    data['fonte'] = 'OpenStreetMap / Nominatim'
    return data


def get_center(path):
    with database(path) as con:
        return public_center(con.execute('SELECT * FROM centro_pesquisa WHERE id=1').fetchone())


def geocode_request(address,structured=None):
    params = urlencode(({'q':address} if structured is None else structured) | {'format':'jsonv2','limit':5,'addressdetails':1})
    request = URLRequest('https://nominatim.openstreetmap.org/search?' + params, headers={
        'User-Agent': 'SonifarmaPrice/1.1.4 (https://github.com/Sonifarma/SonifarmaPrice)',
        'Accept-Language': 'pt-BR,pt;q=0.9',
    })
    with urlopen(request, timeout=20) as response:
        raw = response.read(1_000_001)
    if len(raw)>1_000_000:
        raise ValueError('Resposta geografica excede o limite.')
    result = json.loads(raw)
    if not isinstance(result, list):
        raise ValueError('Resposta geografica invalida.')
    valid = []
    for row in result[:5]:
        try:
            lat, lon = float(row['lat']), float(row['lon'])
            if not isinstance(row['display_name'], str):
                continue
            address = row['display_name'].strip()
            if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180 and address):
                continue
            valid.append({'endereco': address[:1000], 'latitude': lat, 'longitude': lon,
                          'tipo': str(row.get('addresstype') or row.get('type') or '')[:100]})
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    return valid


def mark_approximate_roads(result):
    for item in result:
        if item['tipo'] in {'road','primary','secondary','tertiary','residential','pedestrian','unclassified','service','trunk'}:
            item['tipo']='rua_aproximada'
            item['endereco']='LOCALIZACAO APROXIMADA DA RUA — numero nao confirmado: '+item['endereco']
    return result


def geocode(address):
    result=geocode_request(address)
    if result:return mark_approximate_roads(result)
    # Enderecos fiscais precisam de separadores; complemento e CEP nao sao
    # nomes de rua. Nunca usa ponto da cidade como se fosse a filial.
    parts=[part.strip() for part in address.split(',') if part.strip()]
    if len(parts)<4:return []
    street,number,city,state=parts[:4]
    if not number.isdigit() or len(state)!=2 or not street or not city:return []
    time.sleep(1.05)
    result=geocode_request(address,{'street':number+' '+street,'city':city,'state':state,'country':'Brasil'})
    if result:return mark_approximate_roads(result)
    time.sleep(1.05)
    result=geocode_request(address,{'street':street,'city':city,'state':state,'country':'Brasil'})
    # Um ponto aproximado da rua nao equivale ao numero solicitado.
    for item in result:
        item['tipo']='rua_aproximada'
        item['endereco']='LOCALIZACAO APROXIMADA DA RUA — numero nao confirmado: '+item['endereco']
    return result


def mutation(request, header):
    # Header explicito e mesma origem evitam gravacao por formularios de outros sites.
    if header != '1':
        raise HTTPException(403, 'Acao de cadastro precisa ser enviada pelo painel.')
    origin = request.headers.get('origin')
    if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
        raise HTTPException(403, 'Origem do cadastro nao permitida.')


def make_router(db_path):
    router = APIRouter(prefix='/api/mercado/centro', tags=['Centro da pesquisa'])

    @router.get('')
    def read():
        return {'centro': get_center(db_path())}

    @router.post('/buscar')
    def search(body: AddressSearch, request: Request, x_price_config: str | None = Header(default=None)):
        global last_lookup
        mutation(request, x_price_config)
        query = ' '.join(body.endereco.split())
        if len(query)<8:
            raise HTTPException(422, 'Informe endereco com rua, numero, cidade e estado.')
        cutoff = (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        with database(db_path()) as con:
            con.execute('DELETE FROM centro_candidatos WHERE criado_em < ?', (cutoff,))
            cached = con.execute('SELECT * FROM centro_candidatos WHERE consulta=? AND criado_em>=?', (query.casefold(),cutoff)).fetchall()
        if cached:
            return {'candidatos': [public_center(row) | {'candidato_id':row['id']} for row in cached], 'cache':True}
        if not lock.acquire(blocking=False):
            raise HTTPException(429, 'Busca de endereco em andamento. Aguarde.', headers={'Retry-After':'1'})
        try:
            if time.monotonic()-last_lookup<1:
                raise HTTPException(429, 'Aguarde um segundo antes de buscar outro endereco.', headers={'Retry-After':'1'})
            last_lookup = time.monotonic()
            try:
                candidates = geocode(query)
            except Exception as exc:
                log.exception('Falha no servico geografico do centro da pesquisa')
                raise HTTPException(502, 'Servico de enderecos indisponivel. Tente mais tarde; centro anterior preservado.') from exc
            result = []
            with database(db_path()) as con:
                for item in candidates:
                    token = secrets.token_hex(16)
                    con.execute('INSERT INTO centro_candidatos VALUES(?,?,?,?,?,?,?)',
                                (token,query.casefold(),item['endereco'],item['latitude'],item['longitude'],item['tipo'],now()))
                    result.append(public_center(item) | {'candidato_id':token})
            return {'candidatos':result,'cache':False}
        finally:
            lock.release()

    @router.put('')
    def save(body: CenterSave, request: Request, x_price_config: str | None = Header(default=None)):
        mutation(request, x_price_config)
        with database(db_path()) as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT * FROM centro_candidatos WHERE id=?', (body.candidato_id,)).fetchone()
            if not row or row['criado_em'] < (datetime.now(timezone.utc)-timedelta(days=1)).isoformat():
                raise HTTPException(422, 'Resultado de endereco expirou. Busque novamente e confirme o ponto.')
            previous = con.execute('SELECT * FROM centro_pesquisa WHERE id=1').fetchone()
            version = previous['versao'] if previous else 0
            if version != body.versao:
                raise HTTPException(409, 'O centro foi alterado em outra tela. Recarregue o cadastro antes de salvar.')
            updated = now()
            con.execute('INSERT INTO centro_pesquisa VALUES(1,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET endereco=excluded.endereco,latitude=excluded.latitude,longitude=excluded.longitude,versao=excluded.versao,atualizado_em=excluded.atualizado_em',
                        (row['endereco'],row['latitude'],row['longitude'],version+1,updated))
            current = con.execute('SELECT * FROM centro_pesquisa WHERE id=1').fetchone()
            con.execute('INSERT INTO centro_auditoria(antes,depois,criado_em) VALUES(?,?,?)',
                        (json.dumps(dict(previous) if previous else {}),json.dumps(dict(current)),updated))
        return {'centro':public_center(current)}

    return router
