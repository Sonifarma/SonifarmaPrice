"""Dados publicos renderizados pela Droga Raia; sem checkout, conta ou marketplace."""
from html.parser import HTMLParser
import json,math,re
from urllib.parse import urlencode,urlsplit
from app import composition
from app.product_search import profile,compare,text


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
 except (ValueError,KeyError,TypeError):raise ValueError('Formato da pagina publica Raia nao reconhecido.')
 if not isinstance(data,dict):raise ValueError('Pagina Raia invalida.')
 return data


def product_offer(data,url,ean=None):
 product=data.get('productData')
 if not isinstance(product,dict) or product.get('is3p') is not False or product.get('seller') is not None or str(product.get('status'))!='1':return None
 code=product.get('productEan')
 if not isinstance(code,str) or not re.fullmatch(r'[0-9]{8,14}',code) or (ean and code!=ean):return None
 attrs={item.get('attribute_code'):item.get('value_string') for item in product.get('custom_attributes') or [] if isinstance(item,dict)}
 if attrs.get('ean') and attrs['ean']!=[code]:return None
 slug=attrs.get('url_key') or []
 if len(slug)!=1 or urlsplit(url).path!='/'+slug[0]+'.html':raise ValueError('Pagina Raia diferente do produto solicitado.')
 live=product.get('liveComposition') or {};stock=live.get('liveStock') or {};price_data=live.get('livePrice') or {};aux=product.get('price_aux') or {}
 qty=stock.get('qty')
 if isinstance(qty,bool) or not isinstance(qty,(int,float)) or not math.isfinite(qty) or qty<=0:return None
 price=money(price_data.get('valueTo')) or money(aux.get('value_to'))
 if price is None:return None
 regular=money(aux.get('value_from'));pix=money(price_data.get('pixPrice'))
 condition='Preco publico no site; CEP, frete e disponibilidade a confirmar.'
 if pix and pix<price:
  regular=max(regular or price,price);price=pix;condition='Oferta para pagamento no Pix; CEP, frete e disponibilidade a confirmar.'
 if aux.get('lmpm_qty') and aux.get('lmpm_value_to'):condition+=' Ha desconto por quantidade, nao aplicado a uma unidade.'
 if product.get('pbm') or product.get('pbmOfferTypes') or price_data.get('bestPrice'):condition+=' Beneficios pessoais/PBM ou outros descontos exigem conferencia; nao foram aplicados.'
 title=str(product.get('name') or '')[:300]
 maker=next(iter(attrs.get('fabricante') or attrs.get('marca') or []),'')
 active=next(iter(attrs.get('principioativonovo') or []),None) or None
 if active:active=text(active)
 return {'ean':code,'produto':title,'preco':price,'preco_regular':regular,'em_oferta':bool(regular and price<regular),
  'moeda':'BRL','url':url,'vendedor':'Droga Raia','laboratorio':str(maker)[:100],
  'composicao':composition.signature(title,active),'condicao':condition,'abrangencia':'site_da_rede','filial_confirmada':False}


def search_pages(source,term,fetch,limit=6):
 data=props(fetch(source,'/search?'+urlencode({'w':term})))
 results=(data.get('pageProps') or {}).get('results')
 if not isinstance(results,dict) or not isinstance(results.get('products'),list):raise ValueError('Busca publica Raia nao reconhecida.')
 urls=[]
 for item in results['products']:
  if not isinstance(item,dict) or item.get('is1P') is not True or item.get('isThirdPartner') is not False:continue
  target=urlsplit(str(item.get('url') or ''))
  if target.hostname and target.hostname!=source['host']:continue
  if target.scheme and target.scheme!='https':continue
  if target.username or target.password:continue
  path=target.path
  if not re.fullmatch(r'/[a-z0-9-]+\.html',path):continue
  if path not in urls:urls.append(path)
  if len(urls)==limit:break
 return urls


def offers(source,term,fetch,ean=None,wanted=None,ref=None):
 result=[];seen=set()
 for path in search_pages(source,term,fetch,limit=4 if ean else 6):
  url='https://'+source['host']+path
  offer=product_offer(props(fetch(source,path)),url,ean)
  if not offer or offer['ean'] in seen:continue
  if ref and offer.get('composicao')!=ref:continue
  if wanted:
   match=compare(wanted,offer['produto'],offer['laboratorio'])
   if match is None:continue
   result.append(dict(ean=offer['ean'],produto=offer['produto'],marca=offer['laboratorio'],url=url,oferta=offer,**match))
  else:result.append(offer)
  seen.add(offer['ean'])
  if ean:break
 return result
