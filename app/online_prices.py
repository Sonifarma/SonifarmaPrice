"""Consulta manual a catalogos publicos. Preco de rede nao e preco confirmado da filial."""
from contextlib import closing,contextmanager
from datetime import datetime,timedelta,timezone
import json
import logging
import math
import hashlib
import re
import sqlite3
import threading
import time
from urllib.parse import urlencode,urlsplit,quote
from urllib.request import Request as URLRequest,HTTPRedirectHandler,build_opener
from urllib.robotparser import RobotFileParser
from fastapi import APIRouter,Header,HTTPException,Request
from pydantic import BaseModel,Field
from app.competitors import within_radius,normalized
from app.search_center import get_center,mutation
from app.product_search import profile,compare
from app import composition,todo_dia,raia

SOURCES={
 'drogal':{'nome':'Drogal','host':'www.drogal.com.br','nomes':{'DROGAL'},'cnpj_raiz':'54375647','vendedores':{'DROGAL'}},
 'dsp':{'nome':'Drogaria São Paulo','host':'www.drogariasaopaulo.com.br','nomes':{'DROGARIA SAO PAULO'},'cnpj_raiz':'61412110','vendedores':{'DROGARIA SAO PAULO'}},
 'raia':{'nome':'Droga Raia','host':'www.drogaraia.com.br','nomes':{'DROGA RAIA','RAIA'},'cnpj_raiz':'60746948','cnpj_compartilhado':True,'adaptador':'raia'},
 'tododia':{'nome':'Drogaria Todo Dia','host':'www.drogariatododia.com','nomes':{'DROGARIA TODO DIA','DROGA TODO DIA','DROGARIA TODODIA'},'cnpj_raiz':'12834185','adaptador':'navegador'},
}


AGENT='SonifarmaPrice/1.6.0 (+https://github.com/Sonifarma/SonifarmaPrice)'
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
  con.execute('CREATE TABLE IF NOT EXISTS catalogos_descricao (fonte TEXT,chave TEXT,coletado_em TEXT NOT NULL,candidatos TEXT NOT NULL,PRIMARY KEY(fonte,chave))')
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
 if source.get('adaptador')=='raia':return raia.offers(source,ean,public_document,ean=ean)
 path='/api/catalog_system/pub/products/search?'+urlencode({'fq':'alternateIds_Ean:'+ean})
 return parse_offers(catalog_data(source,path),source,ean)


def public_document(source,path):
 host=source['host']
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
 return fetch_bytes(host,path,2_000_000)


def catalog_data(source,path):
 data=json.loads(public_document(source,path))
 if not isinstance(data,list) or len(data)>50:raise ValueError('Formato inesperado do catalogo.')
 return data


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
    regular=raia.money(offer.get('ListPrice'))
    conditional=any(offer.get(k) for k in ['Teasers','PromotionTeasers','BuyTogether','DiscountHighLight'])
    result.append({'ean':ean,'produto':str(product.get('productName') or item.get('name') or '')[:300],
      'preco':round(price,2),'preco_regular':regular,'em_oferta':bool(regular and price<regular),'moeda':'BRL','url':url,'vendedor':str(seller.get('sellerName'))[:100],
      'condicao':'Preco basico do catalogo; ha promocoes condicionadas a conferir no site.' if conditional else 'Preco do catalogo; condicoes, CEP, frete e disponibilidade a confirmar no site.',
      'abrangencia':'site_da_rede','filial_confirmada':False,
      'laboratorio':str(product.get('brand') or '')[:100],
      'composicao':composition.signature(str(product.get('productName') or item.get('name') or ''),composition.ingredient(product,str(product.get('productName') or item.get('name') or '')))})
 return result[:20]


def query_source(path,key,ean,descricao=""):
 source=SOURCES[key]
 with database(path) as con:row=con.execute('SELECT * FROM catalogos_online WHERE fonte=? AND ean=?',(key,ean)).fetchone()
 cutoff=(datetime.now(timezone.utc)-timedelta(minutes=15)).isoformat()
 if row and row['coletado_em']>=cutoff:
  return {'ofertas':json.loads(row['ofertas']),'coletado_em':row['coletado_em'],'cache':True,'desatualizado':False,'estado':'cache'}
 if not locks[key].acquire(blocking=False):
  return {'ofertas':json.loads(row['ofertas']) if row else [],'coletado_em':row['coletado_em'] if row else None,'cache':bool(row),'desatualizado':True,'estado':'ocupado','mensagem':'Consulta desta fonte em andamento. Aguarde.'}
 try:
  data=todo_dia.lookup(path,profile(descricao) if descricao.strip() else None,ean=ean) if source.get('adaptador')=='navegador' else catalog(source,ean)
  timestamp=min((offer['coletado_em'] for offer in data if offer.get('coletado_em')),default=now())
  with database(path) as con:con.execute('INSERT INTO catalogos_online VALUES(?,?,?,?) ON CONFLICT(fonte,ean) DO UPDATE SET coletado_em=excluded.coletado_em,ofertas=excluded.ofertas',(key,ean,timestamp,json.dumps(data,ensure_ascii=False)))
  return {'ofertas':data,'coletado_em':timestamp,'cache':False,'desatualizado':False,'estado':'consultado'}
 except Exception as exc:
  log.warning('Catalogo publico %s indisponivel (%s)',key,type(exc).__name__)
  return {'ofertas':json.loads(row['ofertas']) if row else [],'coletado_em':row['coletado_em'] if row else None,'cache':bool(row),'desatualizado':True,'estado':'indisponivel',
    'mensagem':str(exc) if isinstance(exc,todo_dia.CatalogNotReady) else 'Fonte indisponivel ou consulta nao permitida. Nenhum preco novo obtido; dados anteriores, quando presentes, mantidos com a data original.'}
 finally:locks[key].release()


def description_catalog(source,wanted):
 if not wanted['consulta']:return []
 if source.get('adaptador')=='raia':return raia.offers(source,wanted['consulta'],public_document,wanted=wanted)
 path='/api/catalog_system/pub/products/search/'+quote(wanted['consulta'],safe='')
 products=catalog_data(source,path);candidates=[];seen=set()
 for product in products:
  if not isinstance(product,dict):continue
  url=public_link(product.get('link'),source['host'])
  if not url:continue
  for item in product.get('items') or []:
   if not isinstance(item,dict):continue
   ean=item.get('ean','')
   if not isinstance(ean,str) or not re.fullmatch(r'[0-9]{8,14}',ean) or ean in seen:continue
   title=str(product.get('productName') or '')[:300]
   match=compare(wanted,title+' '+str(item.get('name') or ''),str(product.get('brand') or ''))
   if match is None:continue
   sku=profile(str(item.get('name') or ''))
   if any(wanted[k] and sku[k] and wanted[k]!=sku[k] for k in ['doses','quantidade','forma']):continue
   if wanted['tamanho']:
    size=re.search(r'\b(XXG|XG|GG|G|M|P)\b',normalized(str(item.get('name') or '')))
    if size and size.group(1)!=wanted['tamanho']:continue
   # parse_offers ainda exige vendedor proprio, disponibilidade e EAN identico no SKU.
   offers=parse_offers([dict(product,items=[item])],source,ean)
   seen.add(ean)
   candidates.append({'ean':ean,'produto':title,'marca':str(product.get('brand') or '')[:100],'url':url,
     'oferta':offers[0] if offers else None,**match})
 return sorted(candidates,key=lambda c:(bool(c['oferta']),c['pontuacao']),reverse=True)[:6]


def query_description(path,key,wanted):
 fingerprint=hashlib.sha256(wanted['descricao'].encode()).hexdigest()
 with database(path) as con:row=con.execute('SELECT * FROM catalogos_descricao WHERE fonte=? AND chave=?',(key,fingerprint)).fetchone()
 cutoff=(datetime.now(timezone.utc)-timedelta(minutes=15)).isoformat()
 if row and row['coletado_em']>=cutoff:
  return {'candidatos':json.loads(row['candidatos']),'coletado_em':row['coletado_em'],'cache':True,'desatualizado':False}
 if not locks[key].acquire(blocking=False):return {'candidatos':[],'coletado_em':None,'cache':False,'desatualizado':False,'mensagem':'Busca por descricao em andamento nesta fonte. Aguarde e atualize.'}
 try:
  candidates=todo_dia.description(path,wanted) if SOURCES[key].get('adaptador')=='navegador' else description_catalog(SOURCES[key],wanted)
  timestamp=min((c['oferta']['coletado_em'] for c in candidates if c.get('oferta') and c['oferta'].get('coletado_em')),default=now())
  with database(path) as con:con.execute('INSERT INTO catalogos_descricao VALUES(?,?,?,?) ON CONFLICT(fonte,chave) DO UPDATE SET coletado_em=excluded.coletado_em,candidatos=excluded.candidatos',(key,fingerprint,timestamp,json.dumps(candidates,ensure_ascii=False)))
  return {'candidatos':candidates,'coletado_em':timestamp,'cache':False,'desatualizado':False}
 except Exception as exc:
  log.warning('Busca por descricao %s indisponivel (%s)',key,type(exc).__name__)
  return {'candidatos':json.loads(row['candidatos']) if row else [],'coletado_em':row['coletado_em'] if row else None,'cache':bool(row),'desatualizado':True,'mensagem':'Busca por descricao indisponivel. Resultados anteriores, quando presentes, mantem a data original.'}
 finally:locks[key].release()


def composition_catalog(source,ref):
 if source.get('adaptador')=='raia':return raia.offers(source,composition.query_text(ref),public_document,ref=ref)
 products=catalog_data(source,'/api/catalog_system/pub/products/search/'+quote(composition.query_text(ref),safe=''))
 offers=[];seen=set()
 for product in products:
  if not isinstance(product,dict):continue
  for item in product.get('items') or []:
   if not isinstance(item,dict):continue
   ean=item.get('ean','')
   if not isinstance(ean,str) or not re.fullmatch(r'[0-9]{8,14}',ean) or ean in seen:continue
   found=parse_offers([dict(product,items=[item])],source,ean)
   for offer in found:
    # O nome do SKU tambem precisa concordar com a apresentacao quando informado.
    sku=profile(str(item.get('name') or ''))
    conflict=any(sku[k] and sku[k]!=ref[target] for k,target in [('doses','doses'),('forma','forma'),('quantidade','quantidade')])
    if offer.get('composicao')==ref and not conflict:
     seen.add(ean);offers.append(offer);break
 return offers[:30]


def query_composition(path,key,ref):
 fingerprint='composicao-v1:'+hashlib.sha256(json.dumps(ref,sort_keys=True).encode()).hexdigest()
 with database(path) as con:row=con.execute('SELECT * FROM catalogos_descricao WHERE fonte=? AND chave=?',(key,fingerprint)).fetchone()
 cutoff=(datetime.now(timezone.utc)-timedelta(minutes=15)).isoformat()
 if row and row['coletado_em']>=cutoff:
  return dict(ofertas=json.loads(row['candidatos']),coletado_em=row['coletado_em'],desatualizado=False,estado='cache')
 if not locks[key].acquire(blocking=False):return dict(ofertas=[],coletado_em=None,desatualizado=False,estado='ocupado')
 try:
  if SOURCES[key].get('adaptador')=='navegador':
   wanted=profile(composition.query_text(ref)+' '+str(ref.get('quantidade') or '')+' '+ref['forma'])
   offers=todo_dia.lookup(path,wanted,ref=ref)
  else:offers=composition_catalog(SOURCES[key],ref)
  timestamp=min((offer['coletado_em'] for offer in offers if offer.get('coletado_em')),default=now())
  with database(path) as con:con.execute('INSERT INTO catalogos_descricao VALUES(?,?,?,?) ON CONFLICT(fonte,chave) DO UPDATE SET coletado_em=excluded.coletado_em,candidatos=excluded.candidatos',(key,fingerprint,timestamp,json.dumps(offers,ensure_ascii=False)))
  return dict(ofertas=offers,coletado_em=timestamp,desatualizado=False,estado='consultado')
 except Exception as exc:
  log.warning('Composicao %s indisponivel (%s)',key,type(exc).__name__)
  return dict(ofertas=json.loads(row['candidatos']) if row else [],coletado_em=row['coletado_em'] if row else None,desatualizado=True,estado='indisponivel')
 finally:locks[key].release()


def composition_results(path,description,ean,sources):
 ref=composition.reference(description,sources,ean)
 if ref is None:return {'referencia':None,'ofertas':[],'fontes':[],'mensagem':'Composicao, concentracao ou apresentacao incompleta. Nao foi possivel comparar outros laboratorios com seguranca.'}
 offers=[];states=[];seen=set()
 for source in sources:
  if source['fonte'] not in SOURCES:continue
  result=query_composition(path,source['fonte'],ref)
  states.append({'rede':source['rede'],'estado':result['estado'],'coletado_em':result['coletado_em']})
  for offer in result['ofertas']:
   identity=(source['fonte'],offer['ean'])
   if identity in seen:continue
   seen.add(identity)
   offers.append(dict(offer,rede=source['rede'],grupo=source['grupo'],coletado_em=result['coletado_em'],desatualizado=result['desatualizado']))
 return {'referencia':ref,'ofertas':offers,'fontes':states,'mensagem':'Comparacao de precos pela composicao e apresentacao informadas no catalogo, independente do laboratorio. Nao indica substituicao de medicamento.'}


class OnlineSearch(BaseModel):
 ean:str|None=Field(default=None,pattern=r'^[0-9]{8,14}$')
 descricao:str=Field(default='',max_length=180)
 selecoes:dict[str,str]=Field(default_factory=dict,max_length=4)
 raio:float=Field(2,ge=.5,le=50)
 centro_versao:int=Field(ge=1)


def matches(store,source):
 name=normalized(store['nome'])
 named=name in source['nomes'] or (source.get('adaptador')=='raia' and name.startswith('DROGA RAIA '))
 return named or bool(not source.get('cnpj_compartilhado') and store.get('cnpj') and store['cnpj'].startswith(source['cnpj_raiz']))



def group_for_stores(stores):
 groups={store['grupo'] for store in stores if store.get('grupo')}
 return next(iter(groups)) if len(groups)==1 else None


def make_router(path,distance):
 router=APIRouter(prefix='/api/mercado/online',tags=['Precos publicos dos sites'])
 @router.post('/consultar')
 def search(body:OnlineSearch,request:Request,x_price_config:str|None=Header(default=None)):
  mutation(request,x_price_config)
  if not body.ean and len(body.descricao.strip())<3:raise HTTPException(422,'Informe EAN ou descricao com ao menos tres caracteres.')
  if any(key not in SOURCES or not re.fullmatch(r'[0-9]{8,14}',value) for key,value in body.selecoes.items()):raise HTTPException(422,'Selecao de produto invalida.')
  wanted=profile(body.descricao) if body.descricao.strip() else None
  center=get_center(path())
  if center is None:raise HTTPException(422,'Cadastre o centro da pesquisa.')
  if center['versao']!=body.centro_versao:raise HTTPException(409,'Centro alterado. Recarregue o cadastro.')
  stores=within_radius(path(),center,body.raio,distance);results=[];supported=set()
  for key,source in SOURCES.items():
   related=[store for store in stores if matches(store,source)]
   if not related:continue
   supported.update(store['id'] for store in related)
   result=query_source(path(),key,body.ean,body.descricao) if body.ean else {'ofertas':[],'coletado_em':None,'cache':False,'desatualizado':False,'estado':'descricao'}
   if wanted and (not result['ofertas'] or key in body.selecoes):
    found=query_description(path(),key,wanted);candidates=found['candidatos']
    selected=body.selecoes.get(key)
    confirmed=next((c for c in candidates if c['ean']==selected and c['oferta']),None) if selected else None
    exact=next((c for c in candidates if c['ean']==body.ean and c['oferta']),None)
    chosen=confirmed or (exact if not selected else None)
    result['candidatos']=candidates
    result['candidatos_coletado_em']=found['coletado_em']
    if chosen:
     result.update(ofertas=[dict(chosen['oferta'],correspondencia='descricao_confirmada' if confirmed else 'ean')],coletado_em=found['coletado_em'],cache=found['cache'],desatualizado=found['desatualizado'],estado='descricao_confirmada' if confirmed else 'ean_por_descricao')
     result.pop('mensagem',None)
    elif selected:result.update(ofertas=[],mensagem='O candidato selecionado nao esta mais disponivel nesta busca. Confira novamente a apresentacao.')
    elif candidates:result['mensagem']='Produtos encontrados por descricao. Confira apresentacao e EAN e escolha o correspondente para incluir o preco no grafico.'
    elif found.get('mensagem'):result['mensagem']=found['mensagem']
    if found.get('desatualizado'):result['aviso_descricao']='Busca por descricao com coleta anterior; confira a data.'
   result.update(fonte=key,rede=source['nome'],grupo=group_for_stores(related),lojas_no_raio=[{'id':s['id'],'nome':s['nome'],'endereco':s['endereco'],'distancia_km':s['distancia_km']} for s in related])
   results.append(result)
  return {'composicao':composition_results(path(),body.descricao,body.ean,results),'ean':body.ean,'centro':center,'raio_km':body.raio,'descricao_original':body.descricao.strip(),'busca_normalizada':wanted['descricao'] if wanted else None,'links_pesquisa':[{'nome':name,'url':'https://www.google.com/search?'+urlencode({'q':'site:'+host+' '+wanted['descricao']})} for name,host in [('Drogasil','www.drogasil.com.br')]] if wanted else [],'fontes':results,'sem_integracao':[s['nome'] for s in stores if s['id'] not in supported],
    'aviso':'Precos dos sites das redes com lojas cadastradas no raio. O valor e a disponibilidade na filial fisica nao foram confirmados. Nao inclui frete ou beneficios pessoais; confira as condicoes na fonte. Estes valores nao sao incorporados ao grafico de observacoes locais.'}
 return router
