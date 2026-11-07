"""Descoberta de estabelecimentos. Nao coleta nem recomenda precos."""
import hmac
from contextlib import contextmanager
import json
import logging
import math
import os
from pathlib import Path
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/api/descoberta', tags=['Descoberta V1.2'])
DB_PATH = Path(__file__).resolve().parents[1] / 'data' / 'mercado.sqlite3'
SOURCE = 'OpenStreetMap / Overpass'
ENDPOINT = 'https://overpass-api.de/api/interpreter'
GROUPS = {'supermercados', 'perfumarias', 'farmacias_redes', 'farmacias_independentes'}
lock = threading.Lock()
last_request = float('-inf')


class Search(BaseModel):
    model_config = ConfigDict(extra='forbid')
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    coordenadas_confirmadas: bool
    raios_km: list[float] = Field(default_factory=lambda: [2, 3, 5, 8, 10], min_length=1, max_length=5)
    quantidade: int = Field(default=10, ge=1, le=100)

    @model_validator(mode='after')
    def validate_search(self):
        if not self.coordenadas_confirmadas:
            raise ValueError('Confirme as coordenadas verificadas da loja.')
        if any(not math.isfinite(r) or not 0.5 <= r <= 10 for r in self.raios_km):
            raise ValueError('Raios devem estar entre 0,5 e 10 km.')
        if self.raios_km != sorted(set(self.raios_km)):
            raise ValueError('Informe raios crescentes, sem repeticao.')
        return self


class Correction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    grupo: str | None = None
    bloqueado: bool
    motivo: str = Field(min_length=3, max_length=300)

    @model_validator(mode='after')
    def validate_group(self):
        if self.grupo is not None and self.grupo not in GROUPS:
            raise ValueError('Grupo invalido.')
        return self


class Connector(Protocol):
    def discover(self, latitude: float, longitude: float, radius: float) -> list[dict]: ...


def distance(a, b, c, d):
    a, b, c, d = map(math.radians, (a, b, c, d))
    v = math.sin((c-a)/2)**2 + math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    return 12742.0176 * math.asin(min(1, math.sqrt(v)))


def classify(tags):
    if tags.get('shop') in {'supermarket', 'wholesale'}:
        return 'supermercados', 'categoria OSM', False
    if tags.get('shop') in {'cosmetics', 'perfumery'}:
        return 'perfumarias', 'categoria OSM', False
    if tags.get('amenity') == 'pharmacy':
        # Marca nao comprova rede; ausencia de marca nao comprova independencia.
        return None, 'farmacia: revisar rede ou independente', True
    return None, 'categoria nao suportada', True


class OverpassConnector:
    def discover(self, latitude, longitude, radius):
        around = f'around:{int(radius*1000)},{latitude},{longitude}'
        query = ('[out:json][timeout:20];('
                 f'nwr["shop"~"^(supermarket|wholesale|cosmetics|perfumery)$"]({around});'
                 f'nwr["amenity"="pharmacy"]({around}););out center tags;')
        req = Request(ENDPOINT, data=urlencode({'data': query}).encode(), headers={
            'User-Agent': 'SonifarmaPrice/1.2 (manual establishment discovery)',
            'Content-Type': 'application/x-www-form-urlencoded',
        })
        with urlopen(req, timeout=30) as response:
            raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise ValueError('Resposta da fonte excede 5 MB.')
        payload = json.loads(raw)
        if payload.get('remark'):
            raise ValueError('Fonte retornou resultado incompleto.')
        if not isinstance(payload.get('elements'), list):
            raise ValueError('Formato inesperado da fonte.')
        return payload['elements']


connector: Connector = OverpassConnector()


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.executescript('''
    CREATE TABLE IF NOT EXISTS descoberta_execucoes (
      id INTEGER PRIMARY KEY, criado_em TEXT NOT NULL, parametros TEXT NOT NULL,
      estado TEXT NOT NULL, resultado TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS descoberta_correcoes (
      fonte_id TEXT PRIMARY KEY, grupo TEXT, bloqueado INTEGER NOT NULL,
      motivo TEXT NOT NULL, atualizado_em TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS descoberta_auditoria (
      id INTEGER PRIMARY KEY, fonte_id TEXT NOT NULL, antes TEXT NOT NULL,
      depois TEXT NOT NULL, criado_em TEXT NOT NULL);
    ''')
    try:
        with con:
            yield con
    finally:
        con.close()


def admin(x_price_token: str | None):
    expected = os.getenv('PRICE_ADMIN_TOKEN', '')
    if not expected:
        raise HTTPException(503, 'Configure PRICE_ADMIN_TOKEN no .env para habilitar descoberta.')
    if not x_price_token or not hmac.compare_digest(x_price_token.encode(), expected.encode()):
        raise HTTPException(401, 'Token de manutencao invalido.')


def now():
    return datetime.now(timezone.utc).isoformat()


def search(params: Search, provider: Connector, corrections=None):
    corrections = corrections or {}
    found = {}
    radii = []
    errors = []
    for radius in params.raios_km:
        radii.append(radius)
        try:
            elements = provider.discover(params.latitude, params.longitude, radius)
            if len(elements) > 10000:
                raise ValueError('Fonte excedeu limite de estabelecimentos.')
            for el in elements:
                tags = el.get('tags') or {}
                center = el.get('center') or el
                try:
                    lat, lon = float(center['lat']), float(center['lon'])
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        continue
                    dist = distance(params.latitude, params.longitude, lat, lon)
                    if dist > radius or not tags.get('name'):
                        continue
                    if el.get('type') not in {'node', 'way', 'relation'}:
                        continue
                    source_id = el['type'] + '/' + str(int(el['id']))
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
                correction = corrections.get(source_id, {})
                group, reason, review = classify(tags)
                if correction.get('grupo'):
                    group, reason, review = correction['grupo'], 'classificacao corrigida pelo operador', False
                found[source_id] = {
                    'fonte_id': source_id, 'nome': str(tags['name'])[:200],
                    'grupo': group, 'revisao_necessaria': review,
                    'classificacao_motivo': reason,
                    'bloqueado': bool(correction.get('bloqueado', False)),
                    'latitude': lat, 'longitude': lon, 'distancia_km': round(dist, 3),
                    'fonte': SOURCE, 'url': 'https://www.openstreetmap.org/' + source_id,
                    'coletado_em': now(), 'confiabilidade': 'cadastro colaborativo; nao verificado em campo',
                }
            valid = [v for v in found.values() if not v['bloqueado'] and v['grupo']]
            if len(valid) >= params.quantidade:
                break
        except Exception:
            logger.exception('Falha na descoberta Overpass (raio %s km)', radius)
            errors.append({'raio_km': radius, 'mensagem': 'Fonte indisponivel ou resposta invalida; tente novamente mais tarde.'})
            break  # Sem retry automatico contra uma fonte indisponivel.
    items = sorted(found.values(), key=lambda x: (x['distancia_km'], x['fonte_id']))
    valid = [v for v in items if not v['bloqueado'] and v['grupo']]
    return {'estado': 'parcial' if errors else 'concluido', 'estabelecimentos': items,
            'validos': len(valid), 'meta_atingida': len(valid) >= params.quantidade,
            'raios_consultados': radii, 'falhas': errors,
            'aviso': 'Distancia em linha reta. Cadastro OSM nao confirma funcionamento, disponibilidade ou precos. Farmacias exigem revisao de grupo.',
            'precos_coletados': False, 'agendamento_ativo': False}


@router.post('/pesquisar')
def discover(params: Search, x_price_token: str | None = Header(default=None)):
    global last_request
    admin(x_price_token)
    if not lock.acquire(blocking=False):
        raise HTTPException(409, 'Ja existe uma descoberta em andamento.')
    try:
        if time.monotonic() - last_request < 60:
            raise HTTPException(429, 'Aguarde um minuto entre pesquisas.', headers={'Retry-After': '60'})
        last_request = time.monotonic()
        with connect() as con:
            corrections = {r['fonte_id']: dict(r) for r in con.execute('SELECT * FROM descoberta_correcoes')}
        result = search(params, connector, corrections)
        with connect() as con:
            cur = con.execute('INSERT INTO descoberta_execucoes(criado_em,parametros,estado,resultado) VALUES(?,?,?,?)',
                              (now(), params.model_dump_json(), result['estado'], json.dumps(result)))
            result['execucao_id'] = cur.lastrowid
        if result['falhas']:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=502, content=result)
        return result
    finally:
        lock.release()


@router.get('/historico')
def history(limit: int = 20, x_price_token: str | None = Header(default=None)):
    admin(x_price_token)
    if not 1 <= limit <= 100:
        raise HTTPException(422, 'Limite entre 1 e 100.')
    with connect() as con:
        rows = con.execute('SELECT * FROM descoberta_execucoes ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return {'execucoes': [dict(r, parametros=json.loads(r['parametros']), resultado=json.loads(r['resultado'])) for r in rows]}


@router.put('/fontes/{tipo}/{identificador}')
def correct(tipo: str, identificador: int, correction: Correction, x_price_token: str | None = Header(default=None)):
    admin(x_price_token)
    if tipo not in {'node', 'way', 'relation'} or identificador <= 0:
        raise HTTPException(422, 'Identificador OSM invalido.')
    key = f'{tipo}/{identificador}'
    data = correction.model_dump()
    with connect() as con:
        before = con.execute('SELECT * FROM descoberta_correcoes WHERE fonte_id=?', (key,)).fetchone()
        con.execute('INSERT INTO descoberta_correcoes VALUES(?,?,?,?,?) ON CONFLICT(fonte_id) DO UPDATE SET grupo=excluded.grupo,bloqueado=excluded.bloqueado,motivo=excluded.motivo,atualizado_em=excluded.atualizado_em',
                    (key, correction.grupo, correction.bloqueado, correction.motivo, now()))
        con.execute('INSERT INTO descoberta_auditoria(fonte_id,antes,depois,criado_em) VALUES(?,?,?,?)',
                    (key, json.dumps(dict(before) if before else {}), json.dumps(data), now()))
    return {'fonte_id': key, **data, 'mensagem': 'Aplicado nas proximas pesquisas; historico anterior preservado.'}
