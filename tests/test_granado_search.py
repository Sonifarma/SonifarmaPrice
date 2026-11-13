import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app import todo_dia as todo
from app.product_search import profile,compare
from test_todo_dia import product,html

URL='https://www.drogariatododia.com/sab-granado-glicer-bebe-90g-p4897-p46609'
TITLE='SABONETE GRANADO GLICERINA BEBE 90G'
DESCRIPTION='SAB INF GRANADO 90G BEBE GLIC'

class GranadoSearchTests(unittest.TestCase):
 def test_abbreviations_match_public_title_without_optional_infantil(self):
  wanted=profile(DESCRIPTION)
  self.assertEqual(wanted['principais'],['SABONETE','GRANADO','BEBE','GLICERINA'])
  self.assertEqual(wanted['doses'],['90G'])
  self.assertIsNotNone(compare(wanted,TITLE,'GRANADO'))
  for title in ['SABONETE GRANADO GLICERINA BEBE 180G','SABONETE LIQUIDO GRANADO GLICERINA BEBE 250ML','SABONETE GRANADO BEBE CAMOMILA 90G','SABONETE GRANADO GLICERINA ADULTO 90G']:
   self.assertIsNone(compare(wanted,title,'GRANADO'),title)
 def test_sitemap_discovery_and_exact_ean_price_reach_lookup(self):
  wanted=profile(DESCRIPTION)
  rows=[dict(url=URL,titulo=TITLE,slug='sab granado glicer bebe 90g')]
  self.assertEqual(todo.rank_urls(rows,wanted),[URL])
  self.assertEqual(todo.rank_urls([dict(url=URL,titulo='sab granado glicer bebe 90g',slug='sab granado glicer bebe 90g')],wanted),[URL])
  data=product();data.update(Name=TITLE,BrandName='GRANADO',Url='/sab-granado-glicer-bebe-90g-p4897-p46609')
  data['Items'][0]['RetailPrice']=7.98
  data['Items'][0]['UPC']='7896512905420'
  ean=data['Items'][0]['UPC']
  with tempfile.TemporaryDirectory() as tmp,patch.object(todo,'Browser') as browser:
   path=Path(tmp)/'catalog.sqlite3'
   with todo.database(path) as con:
    con.execute('INSERT INTO tododia_indice VALUES(1,?)',(json.dumps(['sitemap']),))
    con.execute('INSERT INTO tododia_sitemaps VALUES(?,?,?)',('sitemap',todo.now(),json.dumps(rows)))
   browser.return_value.__enter__.return_value.get.return_value=html(data)
   offers=todo.lookup(path,wanted,ean=ean)
   self.assertEqual(offers[0]['preco'],7.98)
   self.assertEqual(offers[0]['ean'],ean)
   self.assertEqual(todo.lookup(path,wanted,ean='0000000000000'),[])
