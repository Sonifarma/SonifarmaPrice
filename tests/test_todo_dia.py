import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app import todo_dia as todo
from app.product_search import profile

URL='https://www.drogariatododia.com/simeticona-40mg-20cpr-medley-p123-p456'
EAN='7896422505550'

def product():
 return dict(Name='Simeticona 40mg 20 comprimidos Medley',BrandName='Medley',Url='/simeticona-40mg-20cpr-medley-p123-p456',IsPurchasable=True,DisplayPrice='Y',Price={'HasBuyBox':False},Items=[dict(UPC=EAN,RetailPrice=11.99,StockBalance=10,IsPurchasable=True,IsInventoryAvailable=True,Availability='I')])

def html(data):return '<script>var product = '+json.dumps(data)+';</script>'

class TodoDiaTests(unittest.TestCase):
 def test_exact_sku_price_and_ean_no_recommendations_or_duplicate_skus(self):
  data=product();data['Items']*=2
  rows=todo.parse_product(html(data)+'<script>var other = '+json.dumps(product())+'</script>',URL)
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['ean'],EAN);self.assertEqual(rows[0]['preco'],11.99)
  self.assertFalse(rows[0]['filial_confirmada']);self.assertEqual(rows[0]['metodo'],'navegador_publico')
 def test_rejects_hidden_unavailable_marketplace_wrong_url_and_invalid_prices(self):
  for key,value in [('DisplayPrice','N'),('IsPurchasable',False),('Url','/outro-p1'),('Price',{'HasBuyBox':True})]:
   data=product();data[key]=value;self.assertEqual(todo.parse_product(html(data),URL),[],key)
  for key,value in [('RetailPrice',True),('RetailPrice',0),('RetailPrice',float('nan')),('RetailPrice',float('inf')),('StockBalance',0),('Availability','O'),('IsPurchasable',False),('IsInventoryAvailable',False),('UPC','codigo-interno')]:
   data=product();data['Items'][0][key]=value;self.assertEqual(todo.parse_product(html(data),URL),[],(key,value))
  self.assertEqual(todo.parse_product('<script>var product = window.private;</script>',URL),[])
 def test_sitemap_and_target_urls_are_restricted_to_public_pages(self):
  for url in ['http://www.drogariatododia.com/a-p123','https://evil.test/a-p123','https://user@www.drogariatododia.com/a-p123',todo.ORIGIN+'/pesquisa?t=simeticona',todo.ORIGIN+'/painel-do-cliente',todo.ORIGIN+'/sitemap/products/1?x=y']:
   self.assertFalse(todo.safe_url(url),url)
  xml='<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>'+todo.ORIGIN+'/sitemap/products/1</loc></sitemap><sitemap><loc>https://evil.test/1</loc></sitemap></sitemapindex>'
  self.assertEqual(todo.sitemap_pages(xml),[todo.ORIGIN+'/sitemap/products/1'])
  xml='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>'+URL+'</loc></url><url><loc>https://evil.test/1</loc></url></urlset>'
  self.assertEqual(todo.sitemap_products(xml)[0]['url'],URL)
 def test_incomplete_index_does_not_claim_product_absence(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'market.sqlite3'
   with self.assertRaises(todo.CatalogNotReady):todo.load_index(path)
   with todo.database(path) as con:con.execute('INSERT INTO tododia_indice VALUES(1,?)',(json.dumps(['pagina1','pagina2']),))
   with self.assertRaises(todo.CatalogNotReady):todo.load_index(path)
 def test_lookup_only_returns_requested_ean_and_reuses_page_cache(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'market.sqlite3'
   with todo.database(path) as con:
    con.execute('INSERT INTO tododia_indice VALUES(1,?)',(json.dumps(['sitemap']),))
    con.execute('INSERT INTO tododia_sitemaps VALUES(?,?,?)',('sitemap',todo.now(),json.dumps([dict(url=URL,titulo='Simeticona 40mg 20 comprimidos Medley',slug='simeticona 40mg 20cpr medley')])) )
   with patch.object(todo,'Browser') as browser:
    browser.return_value.__enter__.return_value.get.return_value=html(product())
    self.assertEqual(todo.lookup(path,profile('G SIMETICONA 40MG 20CP MEDL'),ean=EAN)[0]['ean'],EAN)
    self.assertEqual(browser.return_value.__enter__.return_value.get.call_count,1)
    with todo.database(path) as con:stored=con.execute('SELECT coletado_em FROM tododia_paginas').fetchone()[0]
   with patch.object(todo,'Browser') as browser:
    result=todo.lookup(path,ean=EAN)[0]
    self.assertEqual(result['preco'],11.99);self.assertEqual(result['coletado_em'],stored)
    browser.return_value.__enter__.return_value.get.assert_not_called()
   with patch.object(todo,'Browser') as browser:
    changed=product();changed['Items'][0]['RetailPrice']=8
    browser.return_value.__enter__.return_value.get.return_value=html(changed)
    self.assertEqual(todo.lookup(path,ean=EAN,force=True)[0]['preco'],8)
    self.assertEqual(browser.return_value.__enter__.return_value.get.call_count,1)
   with patch.object(todo,'Browser') as browser:
    self.assertEqual(todo.lookup(path,profile('G SIMETICONA 40MG 20CP MEDL'),ean='0000000000000'),[])
 def test_ranking_keeps_distinct_strengths_from_winning_over_exact_description(self):
  rows=[dict(url=URL,titulo='Simeticona 40mg 20 comprimidos Medley',slug='simeticona'),dict(url=URL+'1',titulo='Simeticona 125mg 10 capsulas Cimed',slug='simeticona')]
  self.assertEqual(todo.rank_urls(rows,profile('G SIMETICONA 40MG 20CP MEDL'))[0],URL)

 def test_robots_rejection_prevents_navigation(self):
  from unittest.mock import Mock
  from urllib.robotparser import RobotFileParser
  browser=todo.Browser();browser.robots=RobotFileParser();browser.robots.parse(['User-agent: *','Disallow: /simeticona'])
  browser.page=Mock();browser.last=0
  with self.assertRaises(ValueError):browser.get(URL)
  browser.page.goto.assert_not_called()

 def test_changed_page_format_is_not_stored_as_a_fresh_empty_catalog(self):
  with self.assertRaises(todo.ProductFormatError):todo.parse_product('<html>Loja em manutencao</html>',URL,strict=True)
  data=product();data['Items']=[{'ean':EAN,'preco':10}]
  with self.assertRaises(todo.ProductFormatError):todo.parse_product(html(data),URL,strict=True)

 def test_verified_saline_page_can_be_read_without_an_index_and_rejects_different_ean(self):
  ean='7896230304536';url=todo.PUBLIC_PRODUCT_URLS[ean]
  data=product();data['Url']=url.split('.com',1)[1];data['Items'][0]['UPC']=ean
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'local.sqlite3'
   with patch.object(todo,'Browser') as browser:
    browser.return_value.__enter__.return_value.get.return_value=html(data)
    offers=todo.lookup(path,ean=ean,force=True)
   self.assertEqual(offers[0]['ean'],ean)
   data['Items'][0]['UPC']='7890000000000'
   with patch.object(todo,'Browser') as browser:
    browser.return_value.__enter__.return_value.get.return_value=html(data)
    self.assertEqual(todo.lookup(path,ean=ean,force=True),[])
