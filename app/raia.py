"""Dados publicos renderizados pela Droga Raia; sem checkout ou conta; vendedores de marketplace identificados."""
from html.parser import HTMLParser
import json,math,re,logging,os
from pathlib import Path
from urllib.parse import urlencode,urlsplit,parse_qs
from urllib.error import URLError
from app.todo_dia import Browser
from app import composition
from app.product_search import profile,compare,text


# URLs publicas ja verificadas; o EAN e o preco continuam conferidos na pagina.
PUBLIC_PRODUCT_PATHS={'7896230304536':'/adv-solucao-fisiologica-com-10-ampolas.html'}

class RaiaReadError(ValueError):
 def __init__(self,code,message):super().__init__(message);self.code=code


def money(value):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<value<100000:return None
 result=round(float(value),2)
 return result if result>0 else None


class NextData(HTMLParser):
 def __init__(self):super().__init__();self.inside=False;self.parts=[]
 def handle_starttag(self,tag,attrs):
  if tag=='script':self.inside=dict(attrs).get('id')=='__NEXT_DATA__'
 def handle_endtag(self,tag):
  if tag=='script':self.inside=False
 def handle_data(self,data):
  if self.inside:self.parts.append(data)


def props(raw):
 parser=NextData();parser.feed(raw.decode('utf-8') if isinstance(raw,bytes) else raw)
 try:data=json.loads(''.join(parser.parts))['props']['pageProps']
 except (ValueError,KeyError,TypeError):raise RaiaReadError('RAIA_DADOS_PUBLICOS_INVALIDOS','Formato da pagina publica Raia nao reconhecido.')
 if not isinstance(data,dict):raise ValueError('Pagina Raia invalida.')
 return data


def product_identity(data,url,ean=None,allow_marketplace=False):
 product=data.get('productData')
 if not isinstance(product,dict) or str(product.get('status'))!='1':return None
 seller=product.get('seller')
 own=product.get('is3p') is False and seller is None
 partner=allow_marketplace and product.get('is3p') is True and isinstance(seller,dict) and seller.get('active') is True and isinstance(seller.get('storeName'),str) and seller['storeName'].strip() and isinstance(seller.get('id'),str) and seller['id'].strip()
 if not (own or partner):return None
 if re.search(r'\bKIT\b',text(str(product.get('name') or ''))):return None
 code=product.get('productEan')
 if not isinstance(code,str) or not re.fullmatch(r'[0-9]{8,14}',code) or (ean and code!=ean):return None
 attrs={item.get('attribute_code'):item.get('value_string') for item in product.get('custom_attributes') or [] if isinstance(item,dict)}
 if attrs.get('ean') and attrs['ean']!=[code]:return None
 slug=attrs.get('url_key') or []
 if len(slug)!=1 or urlsplit(url).path!='/'+slug[0]+'.html':raise RaiaReadError('RAIA_PAGINA_DIVERGENTE','Pagina Raia diferente do produto solicitado.')
 return product,code,attrs


def product_offer(data,url,ean=None,allow_marketplace=False):
 identity=product_identity(data,url,ean,allow_marketplace)
 if identity is None:return None
 product,code,attrs=identity
 live=product.get('liveComposition') or {};stock=live.get('liveStock') or {};price_data=live.get('livePrice') or {};aux=product.get('price_aux') or {}
 qty=stock.get('qty')
 if isinstance(qty,bool) or not isinstance(qty,(int,float)) or not math.isfinite(qty) or qty<=0:return None
 regular=money(aux.get('value_from'))
 price=money(price_data.get('valueTo')) or money(aux.get('value_to'))
 if price is None and price_data.get('valueTo') is None and aux.get('value_to') is None:price=regular
 if price is None:return None
 pix=money(price_data.get('pixPrice'))
 condition='Preco publico no site; CEP, frete e disponibilidade a confirmar.'
 if pix and pix<price:
  regular=max(regular or price,price);price=pix;condition='Oferta para pagamento no Pix; CEP, frete e disponibilidade a confirmar.'
 if aux.get('lmpm_qty') and aux.get('lmpm_value_to'):condition+=' Ha desconto por quantidade, nao aplicado a uma unidade.'
 if product.get('pbm') or product.get('pbmOfferTypes') or price_data.get('bestPrice'):condition+=' Beneficios pessoais/PBM ou outros descontos exigem conferencia; nao foram aplicados.'
 seller=product.get('seller') if product.get('is3p') is True else None
 if seller:condition+=' Vendido por '+seller['storeName'].strip()[:100]+' no marketplace da Raia; vendedor sem presenca confirmada no raio.'
 title=str(product.get('name') or '')[:300]
 maker=next(iter(attrs.get('fabricante') or attrs.get('marca') or []),'')
 active=next(iter(attrs.get('principioativonovo') or []),None) or None
 if active:active=text(active)
 return {'ean':code,'produto':title,'preco':price,'preco_regular':regular,'em_oferta':bool(regular and price<regular),
  'tipo_preco':'oferta' if regular and price<regular else 'normal','moeda':'BRL','url':url,'vendedor':seller['storeName'].strip()[:100] if seller else 'Droga Raia','marketplace':bool(seller),
  'vendedor_id':seller['id'] if seller else 'raia','grupo_online':'Marketplace — vendedores externos' if seller else None,'laboratorio':str(maker)[:100],
  'composicao':composition.signature(title,active),'condicao':condition,'abrangencia':'marketplace' if seller else 'site_da_rede','filial_confirmada':False}


def search_pages(source,term,fetch,limit=6,allow_marketplace=False):
 data=props(fetch(source,'/search?'+urlencode({'w':term})))
 results=(data.get('pageProps') or {}).get('results')
 if not isinstance(results,dict) or not isinstance(results.get('products'),list):raise RaiaReadError('RAIA_BUSCA_PUBLICA_INVALIDA','Busca publica Raia nao reconhecida.')
 urls=[]
 for item in sorted(results['products'],key=lambda p:not (isinstance(p,dict) and p.get('is1P') is True)):
  if not isinstance(item,dict):continue
  own=item.get('is1P') is True and item.get('isThirdPartner') is False
  partner=allow_marketplace and item.get('is1P') is False and item.get('isThirdPartner') is True
  if not (own or partner) or item.get('isKit') is True or re.search(r'\bKIT\b',text(str(item.get('name') or ''))):continue
  target=urlsplit(str(item.get('url') or ''))
  if target.hostname and target.hostname!=source['host']:continue
  if target.scheme and target.scheme!='https':continue
  if target.username or target.password:continue
  path=target.path
  if not re.fullmatch(r'/[a-z0-9-]+\.html',path):continue
  if path not in urls:urls.append(path)
  if len(urls)==limit:break
 return urls


def _offers(source,term,fetch,ean=None,wanted=None,ref=None):
 result=[];seen=set()
 if ean in PUBLIC_PRODUCT_PATHS:
  path=PUBLIC_PRODUCT_PATHS[ean];url='https://'+source['host']+path
  try:known=product_offer(props(fetch(source,path)),url,ean)
  except (URLError,TimeoutError,ValueError):known=None
  if known:return [known]
 for path in search_pages(source,term,fetch,limit=6,allow_marketplace=True):
  url='https://'+source['host']+path
  data=props(fetch(source,path))
  offer=product_offer(data,url,ean,allow_marketplace=True)
  if not offer:
   # Produto proprio identificado, mas sem disponibilidade: permite conferir
   # o catalogo sem transformar preco de referencia em oferta compravel.
   identity=product_identity(data,url,ean)
   if wanted and identity:
    product,code,attrs=identity
    qty=((product.get('liveComposition') or {}).get('liveStock') or {}).get('qty')
    if not isinstance(qty,bool) and isinstance(qty,(int,float)) and qty==0 and code not in seen:
     title=str(product.get('name') or '')[:300]
     maker=str(next(iter(attrs.get('fabricante') or attrs.get('marca') or []),''))[:100]
     match=compare(wanted,title,maker)
     if match is not None:
      match['pendencias'].append('Catalogo sem disponibilidade confirmada; consulte CEP e estoque no site')
      result.append(dict(ean=code,produto=title,marca=maker,url=url,oferta=None,**match));seen.add(code)
   continue
  identity=(offer['ean'],offer['vendedor_id'])
  if identity in seen:continue
  if ref and offer.get('composicao')!=ref:continue
  if wanted:
   match=compare(wanted,offer['produto'],offer['laboratorio'])
   if match is None:continue
   result.append(dict(ean=offer['ean'],produto=offer['produto'],marca=offer['laboratorio'],url=url,oferta=offer,**match))
  else:result.append(offer)
  seen.add(identity)
 return result


def browser_url(url):
 try:
  parsed=urlsplit(url)
  if parsed.scheme!='https' or parsed.hostname!='www.drogaraia.com.br' or parsed.port not in {None,443} or parsed.username or parsed.password or parsed.fragment or '\\' in url or any(ord(c)<33 for c in url):return False
  if parsed.path=='/search':
   query=parse_qs(parsed.query,max_num_fields=1)
   return set(query)=={'w'} and len(query['w'])==1 and 0<len(query['w'][0])<=300
  return not parsed.query and (parsed.path=='/robots.txt' or bool(re.fullmatch(r'/[a-z0-9-]+\.html',parsed.path)))
 except (ValueError,TypeError):return False


def browser_mode(platform=None):
 mode=os.getenv('PRICE_RAIA_BROWSER_MODE','auto').strip().lower()
 if mode not in {'auto','visible','headless'}:raise RaiaReadError('MODO_NAVEGADOR_INVALIDO','Modo Raia invalido: use auto, visible ou headless.')
 return mode=='visible' or (mode=='auto' and (platform or os.name)=='nt')


def system_browser(platform=None):
 configured=os.getenv('PRICE_BROWSER_EXECUTABLE','').strip()
 if configured:return configured
 if (platform or os.name)=='nt':
  candidates=[Path(os.getenv('ProgramFiles','C:/Program Files'))/'Google/Chrome/Application/chrome.exe',
   Path(os.getenv('LOCALAPPDATA','C:/Users/Default/AppData/Local'))/'Google/Chrome/Application/chrome.exe',
   Path(os.getenv('ProgramFiles(x86)','C:/Program Files (x86)'))/'Google/Chrome/Application/chrome.exe',
   Path(os.getenv('ProgramFiles(x86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
   Path(os.getenv('ProgramFiles','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']
  return next((str(path) for path in candidates if path.is_file()),None)
 return None


def offers(source,term,fetch,ean=None,wanted=None,ref=None):
 try:return _offers(source,term,fetch,ean,wanted,ref)
 except (URLError,TimeoutError,ValueError) as exc:
  logging.getLogger(__name__).warning('Raia: acesso direto indisponivel (%s); tentando navegador publico.',type(exc).__name__)
  with standard_browser(source['host']) as browser:
   result=_offers(source,term,lambda source,path:browser.get('https://'+source['host']+path),ean,wanted,ref)
  for row in result:
   offer=row.get('oferta',row)
   if offer is not None:offer['metodo']='navegador_publico'
  return result


class RaiaBrowser(Browser):
 def __init__(self,host):super().__init__(host=host,validator=browser_url,render=True,visible=browser_mode())
 def __enter__(self):
  self.preferred_executable=system_browser()
  return super().__enter__()


def standard_browser(host):return RaiaBrowser(host)
