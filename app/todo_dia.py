"""Catalogo publico Todo Dia por Chromium e sitemap; nao usa pesquisa bloqueada no robots."""
from contextlib import closing,contextmanager,ExitStack
from datetime import datetime,timedelta,timezone
from html.parser import HTMLParser
import argparse,json,math,os,re,sqlite3,time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET
from app.product_search import profile,compare,text
from app import composition

HOST='www.drogariatododia.com'
ORIGIN='https://'+HOST
AGENT='SonifarmaPrice'
class CatalogNotReady(ValueError):pass
class ProductFormatError(ValueError):pass

NS={'s':'http://www.sitemaps.org/schemas/sitemap/0.9','i':'http://www.google.com/schemas/sitemap-image/1.1'}


def now():return datetime.now(timezone.utc).isoformat()


def safe_url(url):
 try:
  p=urlsplit(url)
  return bool(p.scheme=='https' and p.hostname==HOST and p.port in {None,443} and not p.username and not p.password and not p.query and not p.fragment and not any(ord(c)<33 for c in url) and '\\' not in url and (p.path=='/robots.txt' or p.path=='/sitemap/index' or re.fullmatch(r'/sitemap/products/\d+',p.path) or re.fullmatch(r'/[a-z0-9-]+-p\d+',p.path)))
 except (ValueError,TypeError):return False


@contextmanager
def database(path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with closing(sqlite3.connect(path,timeout=10)) as con:
  con.row_factory=sqlite3.Row
  con.execute('CREATE TABLE IF NOT EXISTS tododia_sitemaps (url TEXT PRIMARY KEY, coletado_em TEXT NOT NULL, produtos TEXT NOT NULL)')
  con.execute('CREATE TABLE IF NOT EXISTS tododia_paginas (url TEXT PRIMARY KEY, coletado_em TEXT NOT NULL, ofertas TEXT NOT NULL)')
  con.execute('CREATE TABLE IF NOT EXISTS tododia_indice (id INTEGER PRIMARY KEY CHECK(id=1), paginas TEXT NOT NULL)')
  with con:yield con


class Browser:
 def __init__(self,host=HOST,validator=safe_url):
  self.origin='https://'+host;self.allowed_url=validator
 def __enter__(self):
  from playwright.sync_api import sync_playwright
  self.driver=sync_playwright().start()
  options={'headless':True}
  proxy=os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
  if proxy:options['proxy']={'server':proxy}
  executable=os.getenv('PRICE_BROWSER_EXECUTABLE','').strip()
  if executable:options['executable_path']=executable
  elif os.name!='nt' and Path('/usr/bin/chromium').exists():options['executable_path']='/usr/bin/chromium'
  self.browser=None
  try:
   self.browser=self.driver.chromium.launch(**options)
   self.context=self.browser.new_context(java_script_enabled=False,accept_downloads=False)
   # Apenas documentos publicos: sem anuncios, rastreadores, scripts ou imagens.
   self.context.route('**/*',lambda route:route.continue_() if route.request.resource_type=='document' and self.allowed_url(route.request.url) else route.abort())
   self.page=self.context.new_page();self.last=0;self.robots=None
   raw=self.get(self.origin+'/robots.txt')
   self.robots=RobotFileParser();self.robots.parse(raw.splitlines())
   return self
  except Exception:
   self.__exit__(None,None,None);raise
 def __exit__(self,*args):
  try:
   if self.browser:self.browser.close()
  finally:self.driver.stop()
 def get(self,url):
  if not self.allowed_url(url):raise ValueError('URL fora do catalogo publico cadastrado.')
  if self.robots and not self.robots.can_fetch(AGENT,url):raise ValueError('Caminho nao permitido pela fonte.')
  delay=max(1,self.robots.crawl_delay(AGENT) or 0) if self.robots else 1
  remaining=delay-(time.monotonic()-self.last)
  if remaining>0:time.sleep(remaining)
  self.last=time.monotonic()
  response=self.page.goto(url,wait_until='domcontentloaded',timeout=25000)
  if response is None or response.status!=200 or not self.allowed_url(self.page.url):raise ValueError('Documento publico indisponivel.')
  raw=response.body()
  if len(raw)>3_000_000:raise ValueError('Documento excede o limite.')
  return raw.decode('utf-8-sig')


def sitemap_pages(raw):
 root=ET.fromstring(raw)
 pages=[node.text.strip() for node in root.findall('s:sitemap/s:loc',NS) if node.text and re.fullmatch(r'https://www\.drogariatododia\.com/sitemap/products/\d+',node.text.strip())]
 if not pages or len(pages)>500:raise ValueError('Indice publico inesperado.')
 return list(dict.fromkeys(pages))


def sitemap_products(raw):
 result=[]
 for row in ET.fromstring(raw).findall('s:url',NS):
  url=row.findtext('s:loc',default='',namespaces=NS).strip()
  if not safe_url(url) or '/sitemap/' in url:continue
  title=row.findtext('i:image/i:title',default='',namespaces=NS).strip()
  slug=re.sub(r'-p\d+(?:-p\d+)?$','',urlsplit(url).path.strip('/')).replace('-',' ')
  result.append({'url':url,'titulo':title[:350] if title else slug[:350],'slug':slug[:350]})
 if len(result)>1000:raise ValueError('Pagina de indice excede o limite.')
 return result


def prepare(path,progress=print,refresh=False):
 with Browser() as browser:
  pages=sitemap_pages(browser.get(ORIGIN+'/sitemap/index'))
  with database(path) as con:con.execute('INSERT INTO tododia_indice VALUES(1,?) ON CONFLICT(id) DO UPDATE SET paginas=excluded.paginas',(json.dumps(pages),))
  cutoff=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
  for index,url in enumerate(pages,1):
   with database(path) as con:cached=con.execute('SELECT coletado_em FROM tododia_sitemaps WHERE url=?',(url,)).fetchone()
   if refresh or cached is None or cached['coletado_em']<cutoff:
    products=sitemap_products(browser.get(url))
    with database(path) as con:con.execute('INSERT INTO tododia_sitemaps VALUES(?,?,?) ON CONFLICT(url) DO UPDATE SET coletado_em=excluded.coletado_em,produtos=excluded.produtos',(url,now(),json.dumps(products,ensure_ascii=False)))
   if index==1 or index%10==0 or index==len(pages):progress(f'Catalogo Todo Dia: {index}/{len(pages)} paginas preparadas.')
 return len(load_index(path))


def load_index(path):
 with database(path) as con:
  expected=con.execute('SELECT paginas FROM tododia_indice WHERE id=1').fetchone()
  rows={r['url']:json.loads(r['produtos']) for r in con.execute('SELECT * FROM tododia_sitemaps')}
 if expected is None or any(url not in rows for url in json.loads(expected['paginas'])):
  raise CatalogNotReady('Catalogo Todo Dia ainda precisa ser preparado no servidor; consulte o guia da integracao.')
 result={}
 for page in json.loads(expected['paginas']):
  for product in rows[page]:result[product['url']]=product
 return list(result.values())


class ProductScripts(HTMLParser):
 def __init__(self):super().__init__();self.inside=False;self.scripts=[];self.parts=[]
 def handle_starttag(self,tag,attrs):
  if tag=='script':self.inside=True;self.parts=[]
 def handle_endtag(self,tag):
  if tag=='script' and self.inside:self.scripts.append(''.join(self.parts));self.inside=False
 def handle_data(self,data):
  if self.inside:self.parts.append(data)


def parse_product(raw,url,strict=False):
 if not safe_url(url):return []
 parser=ProductScripts();parser.feed(raw);product=None
 for script in parser.scripts:
  match=re.match(r'\s*var\s+product\s*=\s*',script)
  if match:
   try:product,_=json.JSONDecoder().raw_decode(script[match.end():])
   except (ValueError,RecursionError):
    if strict:raise ProductFormatError('Formato do produto publico mudou.')
    return []
   break
 if not isinstance(product,dict) or not {'IsPurchasable','DisplayPrice','Url','Price','Items','Name'}.issubset(product):
  if strict:raise ProductFormatError('Dados do produto nao identificados na pagina.')
  return []
 if product.get('IsPurchasable') is not True or product.get('DisplayPrice')!='Y':return []
 if product.get('Url')!=urlsplit(url).path:
  if strict:raise ProductFormatError('Pagina redirecionada ou produto diferente do solicitado.')
  return []
 pricing=product.get('Price') or {}
 if not isinstance(pricing,dict) or pricing.get('HasBuyBox') is not False:return []
 title=str(product.get('Name') or '')[:300];brand=str(product.get('BrandName') or '')[:100]
 if not title:return []
 if not isinstance(product['Items'],list) or not any(isinstance(row,dict) and 'UPC' in row for row in product['Items']):
  if strict:raise ProductFormatError('Formato dos SKUs do produto nao reconhecido.')
  return []
 rows=product['Items'];seen=set();offers=[]
 for row in rows[:100]:
  if not isinstance(row,dict):continue
  ean=row.get('UPC');price=row.get('RetailPrice');stock=row.get('StockBalance')
  if not isinstance(ean,str) or not re.fullmatch(r'[0-9]{8,14}',ean) or ean in seen:continue
  if row.get('IsPurchasable') is not True or row.get('IsInventoryAvailable') is not True or row.get('Availability')!='I':continue
  if isinstance(price,bool) or not isinstance(price,(int,float)) or not math.isfinite(price) or not 0<price<100000:continue
  if isinstance(stock,bool) or not isinstance(stock,(int,float)) or not math.isfinite(stock) or stock<=0:continue
  if round(price,2)<=0:continue
  promotional=row.get('PromotionPrice')
  if not isinstance(promotional,bool) and isinstance(promotional,(int,float)) and math.isfinite(promotional) and 0<round(promotional,2)<price:price=round(promotional,2)
  regular=row.get('ListPrice')
  regular=round(regular,2) if not isinstance(regular,bool) and isinstance(regular,(int,float)) and math.isfinite(regular) and 0<regular<100000 else None
  seen.add(ean)
  offers.append({'ean':ean,'produto':title,'preco':round(price,2),'preco_regular':regular,'em_oferta':bool(regular and price<regular),'moeda':'BRL','url':url,'vendedor':'Drogaria Todo Dia',
   'laboratorio':brand,'composicao':composition.signature(title),'abrangencia':'site_da_rede','filial_confirmada':False,
   'condicao':'Preco publico no site; CEP, frete, PBM, descontos por quantidade e disponibilidade a confirmar.','metodo':'navegador_publico'})
 return offers


def rank_urls(products,wanted,limit=8):
 keys=wanted['principais']
 if not keys:return []
 ranked=[]
 for product in products:
  title=product['titulo']+' '+product['slug'];expanded=text(title)
  if any(not re.search(r'\b'+re.escape(word)+r'\b',expanded) for word in keys):continue
  actual=profile(title)
  score=sum(5 for k in ['doses','quantidade','forma'] if wanted[k] and wanted[k]==actual[k])
  if wanted.get('fabricante') and wanted['fabricante'] in expanded:score+=8
  ranked.append((score,product['url']))
 return [url for score,url in sorted(ranked,key=lambda row:(-row[0],row[1]))[:limit]]


def lookup(path,wanted=None,ean=None,ref=None,force=False):
 products=load_index(path)
 with database(path) as con:rows=con.execute('SELECT * FROM tododia_paginas').fetchall()
 cached={r['url']:r for r in rows}
 # EAN ja conhecido pode ser atualizado sem repetir a descoberta por descricao.
 known=[row['url'] for row in rows if ean and any(o.get('ean')==ean for o in json.loads(row['ofertas']))]
 urls=list(dict.fromkeys(known+rank_urls(products,wanted)))[:8] if wanted else known[:8]
 cutoff=(datetime.now(timezone.utc)-timedelta(minutes=15)).isoformat()
 offers=[]
 with ExitStack() as stack:
  browser=None
  for url in urls:
   row=cached.get(url)
   if not force and row and row['coletado_em']>=cutoff:found=json.loads(row['ofertas'])
   else:
    if browser is None:browser=stack.enter_context(Browser())
    found=parse_product(browser.get(url),url,strict=True)
    collected=now()
    with database(path) as con:con.execute('INSERT INTO tododia_paginas VALUES(?,?,?) ON CONFLICT(url) DO UPDATE SET coletado_em=excluded.coletado_em,ofertas=excluded.ofertas',(url,collected,json.dumps(found,ensure_ascii=False)))
   timestamp=row['coletado_em'] if not force and row and row['coletado_em']>=cutoff else collected
   offers.extend(dict(offer,coletado_em=timestamp) for offer in found)
   if ean and any(o['ean']==ean for o in found):break
 if ref:offers=[o for o in offers if o.get('composicao')==ref]
 elif ean:offers=[o for o in offers if o['ean']==ean]
 return offers


def description(path,wanted,force=False):
 candidates=[]
 for offer in lookup(path,wanted,force=force):
  match=compare(wanted,offer['produto'],offer['laboratorio'])
  if match:candidates.append(dict(ean=offer['ean'],produto=offer['produto'],marca=offer['laboratorio'],url=offer['url'],oferta=offer,**match))
 return candidates[:8]


def main():
 from dotenv import load_dotenv
 root=Path(__file__).resolve().parent.parent;load_dotenv(root/'.env')
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('acao',choices=['preparar']);parser.add_argument('--atualizar',action='store_true');args=parser.parse_args()
 total=prepare(root/'data'/'mercado.sqlite3',progress=lambda message:print(message,flush=True),refresh=args.atualizar)
 print(f'Catalogo pronto: {total} produtos publicos. Os precos serao coletados durante as consultas.')


if __name__=='__main__':main()
