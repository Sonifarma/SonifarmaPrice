"""Consulta manual a catalogos publicos. Preco de rede nao e preco confirmado da filial."""
from contextlib import closing,contextmanager
from datetime import datetime,timedelta,timezone
import json
import logging
import math
import sqlite3
import threading
import time
from urllib.parse import urlencode,urlsplit
from urllib.request import Request as URLRequest,HTTPRedirectHandler,build_opener
from urllib.robotparser import RobotFileParser
from fastapi import APIRouter,Header,HTTPException,Request
from pydantic import BaseModel,Field
from app.competitors import within_radius,normalized
from app.search_center import get_center,mutation

SOURCES={
 'drogal':{'nome':'Drogal','host':'www.drogal.com.br','nomes':{'DROGAL'},'cnpj_raiz':'54375647','vendedores':{'DROGAL'}},
 'dsp':{'nome':'Drogaria São Paulo','host':'www.drogariasaopaulo.com.br','nomes':{'DROGARIA SAO PAULO'},'cnpj_raiz':'61412110','vendedores':{'DROGARIA SAO PAULO'}},
}
MANUAL_SOURCES={'tododia':{'nome':'Drogaria Todo Dia','host':'www.drogariatododia.com',
 'nomes':{'DROGARIA TODO DIA','DROGA TODO DIA','DROGARIA TODODIA'},'cnpj_raiz':'12834185'}}

AGENT='SonifarmaPrice/1.2.1 (+https://github.com/Sonifarma/SonifarmaPrice)'
log=logging.getLogger(__name__)
locks={key:threading.Lock() for key in SOURCES}
last_request={}
robots_cache={}


def now():return datetime.now(timezone.utc).isoformat()


@contextmanager
def database(path):
 path.parent.mkdir(parents=True,exist_ok=True)
 with closing(sqlite3.connect(path,timeout=10)) as con:
  con.row_factory=sqlite3.Row
  con.execute('CREATE TABLE IF NOT EXISTS catalogos_online (fonte TEXT,ean TEXT,coletado_em TEXT NOT NULL,ofertas TEXT NOT NULL,PRIMARY KEY(fonte,ean))')
  with con:yield con


class SameHostRedirect(HTTPRedirectHandler):
 def __init__(self,host):self.host=host
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if not public_link(newurl,self.host):raise ValueError('Redirecionamento fora da fonte cadastrada.')
  return super().redirect_request(req,fp,code,msg,headers,newurl)


def public_link(value,host):
 if not isinstance(value,str) or len(value)>2048 or any(ord(c)<33 for c in value) or '\\' in value:return None
 try:
  url=urlsplit(value)
  return value if url.scheme=='https' and url.hostname==host and url.port in {None,443} and not url.username and not url.password else None
 except ValueError:return None


def fetch_bytes(host,path,limit):
 delay=1-(time.monotonic()-last_request.get(host,float('-inf')))
 if delay>0:time.sleep(delay)
 last_request[host]=time.monotonic()
 request=URLRequest('https://'+host+path,headers={'User-Agent':AGENT,'Accept':'application/json,text/plain;q=0.9'})
 with build_opener(SameHostRedirect(host)).open(request,timeout=12) as response:raw=response.read(limit+1)
 if len(raw)>limit:raise ValueError('Resposta da fonte excede o limite.')
 return raw


def catalog(source,ean):
 host=source['host'];path='/api/catalog_system/pub/products/search?'+urlencode({'fq':'alternateIds_Ean:'+ean})
 cached=robots_cache.get(host)
 if not cached or time.monotonic()-cached[0]>86400:
  raw=fetch_bytes(host,'/robots.txt',200_000)
  parser=RobotFileParser();parser.parse(raw.decode('utf-8').splitlines())
  robots_cache[host]=(time.monotonic(),parser)
 else:parser=cached[1]
 if not parser.can_fetch(AGENT,'https://'+host+path):raise ValueError('Fonte nao permite a consulta automatizada neste caminho.')
 crawl=parser.crawl_delay(AGENT) or 0
 if crawl>1:
  delay=crawl-(time.monotonic()-last_request.get(host,float('-inf')))
  if delay>0:raise ValueError('Intervalo solicitado pela fonte; tente mais tarde.')
 raw=fetch_bytes(host,path,2_000_000)
 data=json.loads(raw)
 if not isinstance(data,list) or len(data)>50:raise ValueError('Formato inesperado do catalogo.')
 return parse_offers(data,source,ean)


def parse_offers(products,source,ean):
 result=[];seen=set()
 for product in products:
  if not isinstance(product,dict):continue
  url=public_link(product.get('link'),source['host'])
  if not url:continue
  for item in product.get('items') or []:
   if not isinstance(item,dict) or item.get('ean')!=ean:continue
   for seller in item.get('sellers') or []:
    if not isinstance(seller,dict) or str(seller.get('sellerId'))!='1' or normalized(seller.get('sellerName','')) not in source['vendedores']:continue
    offer=seller.get('commertialOffer') or {}
    price=offer.get('Price');quantity=offer.get('AvailableQuantity')
    if offer.get('IsAvailable') is not True or offer.get('CurrencyCode','BRL')!='BRL':continue
    if isinstance(price,bool) or not isinstance(price,(int,float)) or not math.isfinite(price) or not 0<price<100000:continue
    if isinstance(quantity,bool) or not isinstance(quantity,(int,float)) or not math.isfinite(quantity) or quantity<=0:continue
    price=round(price,2)
    if price<=0:continue
    key=(url,str(item.get('itemId','')),ean)
    if key in seen:continue
    seen.add(key)
    conditional=any(offer.get(k) for k in ['Teasers','PromotionTeasers','BuyTogether','DiscountHighLight'])
    result.append({'ean':ean,'produto':str(product.get('productName') or item.get('name') or '')[:300],
      'preco':round(price,2),'moeda':'BRL','url':url,'vendedor':str(seller.get('sellerName'))[:100],
      'condicao':'Preco basico do catalogo; ha promocoes condicionadas a conferir no site.' if conditional else 'Preco do catalogo; condicoes, CEP, frete e disponibilidade a confirmar no site.',
      'abrangencia':'site_da_rede','filial_confirmada':False})
 return result[:20]


def query_source(path,key,ean):
 source=SOURCES[key]
 with database(path) as con:row=con.execute('SELECT * FROM catalogos_online WHERE fonte=? AND ean=?',(key,ean)).fetchone()
 cutoff=(datetime.now(timezone.utc)-timedelta(minutes=15)).isoformat()
 if row and row['coletado_em']>=cutoff:
  return {'ofertas':json.loads(row['ofertas']),'coletado_em':row['coletado_em'],'cache':True,'desatualizado':False,'estado':'cache'}
 if not locks[key].acquire(blocking=False):
  return {'ofertas':json.loads(row['ofertas']) if row else [],'coletado_em':row['coletado_em'] if row else None,'cache':bool(row),'desatualizado':True,'estado':'ocupado','mensagem':'Consulta desta fonte em andamento. Aguarde.'}
 try:
  data=catalog(source,ean);timestamp=now()
  with database(path) as con:con.execute('INSERT INTO catalogos_online VALUES(?,?,?,?) ON CONFLICT(fonte,ean) DO UPDATE SET coletado_em=excluded.coletado_em,ofertas=excluded.ofertas',(key,ean,timestamp,json.dumps(data,ensure_ascii=False)))
  return {'ofertas':data,'coletado_em':timestamp,'cache':False,'desatualizado':False,'estado':'consultado'}
 except Exception as exc:
  log.warning('Catalogo publico %s indisponivel (%s)',key,type(exc).__name__)
  return {'ofertas':json.loads(row['ofertas']) if row else [],'coletado_em':row['coletado_em'] if row else None,'cache':bool(row),'desatualizado':True,'estado':'indisponivel',
    'mensagem':'Fonte indisponivel ou consulta nao permitida. Nenhum preco novo obtido; dados anteriores, quando presentes, mantidos com a data original.'}
 finally:locks[key].release()


class OnlineSearch(BaseModel):
 ean:str=Field(pattern=r'^[0-9]{8,14}$')
 raio:float=Field(2,ge=.5,le=50)
 centro_versao:int=Field(ge=1)


def matches(store,source):
 return normalized(store['nome']) in source['nomes'] or bool(store.get('cnpj') and store['cnpj'].startswith(source['cnpj_raiz']))


def make_router(path,distance):
 router=APIRouter(prefix='/api/mercado/online',tags=['Precos publicos dos sites'])
 @router.post('/consultar')
 def search(body:OnlineSearch,request:Request,x_price_config:str|None=Header(default=None)):
  mutation(request,x_price_config)
  center=get_center(path())
  if center is None:raise HTTPException(422,'Cadastre o centro da pesquisa.')
  if center['versao']!=body.centro_versao:raise HTTPException(409,'Centro alterado. Recarregue o cadastro.')
  stores=within_radius(path(),center,body.raio,distance);results=[];supported=set()
  for key,source in SOURCES.items():
   related=[store for store in stores if matches(store,source)]
   if not related:continue
   supported.update(store['id'] for store in related)
   result=query_source(path(),key,body.ean)
   result.update(fonte=key,rede=source['nome'],lojas_no_raio=[{'id':s['id'],'nome':s['nome'],'endereco':s['endereco'],'distancia_km':s['distancia_km']} for s in related])
   results.append(result)
  for key,source in MANUAL_SOURCES.items():
   related=[store for store in stores if matches(store,source)]
   if not related:continue
   supported.update(store['id'] for store in related)
   results.append({'fonte':key,'rede':source['nome'],'estado':'consulta_manual','ofertas':[],
    'coletado_em':None,'cache':False,'desatualizado':False,'url_consulta':'https://'+source['host']+'/',
    'mensagem':'Consulta automatica pendente. O teste de acesso respondeu HTTP 403; abra o site e pesquise o EAN manualmente. Nenhum preco foi coletado desta fonte.',
    'lojas_no_raio':[{'id':s['id'],'nome':s['nome'],'endereco':s['endereco'],'distancia_km':s['distancia_km']} for s in related]})
  return {'ean':body.ean,'centro':center,'raio_km':body.raio,'fontes':results,'sem_integracao':[s['nome'] for s in stores if s['id'] not in supported],
    'aviso':'Precos dos sites das redes com lojas cadastradas no raio. O valor e a disponibilidade na filial fisica nao foram confirmados. Nao inclui frete ou beneficios pessoais; confira as condicoes na fonte. Estes valores nao sao incorporados ao grafico de observacoes locais.'}
 return router
