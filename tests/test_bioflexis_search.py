import unittest
from unittest.mock import patch
from app import online_prices as online, raia
from app.product_search import profile, compare
from test_raia import data, document, URL

class BioflexisTests(unittest.TestCase):
 def test_abbreviations_preserve_pack_and_manufacturer(self):
  wanted=profile('BIOFLEXIS 40MG 60CPS UNIAOQ')
  self.assertEqual(wanted['quantidade'],60)
  self.assertEqual(wanted['forma'],'CAPSULAS')
  self.assertEqual(wanted['fabricante'],'UNIAO QUIMICA')
  self.assertEqual(wanted['principais'],['BIOFLEXIS'])
  match=compare(wanted,'Colágeno Não Hidrolisado Tipo II 40mg Bioflexis com 60 cápsulas','')
  self.assertIsNotNone(match)
  self.assertTrue(match['pendencias'])
  for title in ['Bioflexis 40mg 30 cápsulas','Bioflexis 80mg 60 cápsulas','Bioflexis 40mg 60 cápsulas EMS']:
   self.assertIsNone(compare(wanted,title,''))
 def test_broader_search_keeps_original_matching_profile(self):
  wanted=profile('BIOFLEXIS 40MG 60CPS UNIAOQ')
  with patch.object(online,'description_catalog_query',side_effect=[[],[{'ean':'7896006214748'}]]) as query:
   self.assertEqual(online.description_catalog(online.SOURCES['drogal'],wanted),[{'ean':'7896006214748'}])
  self.assertEqual(query.call_args_list[1].args[2],'bioflexis')
  self.assertEqual(query.call_args_list[1].args[1],wanted)
 def test_unavailable_own_product_is_candidate_without_price(self):
  product=data();product['productData']['liveComposition']['liveStock']['qty']=0
  search={'pageProps':{'results':{'products':[{'url':'/produto-teste.html','is1P':True,'isThirdPartner':False}]}}}
  def fetch(source,path):return document(search if path.startswith('/search?') else product)
  candidates=raia.offers(online.SOURCES['raia'],'simeticona',fetch,wanted=profile('G SIMETICONA 40MG 20CP MEDL'))
  self.assertEqual(len(candidates),1)
  self.assertIsNone(candidates[0]['oferta'])
  self.assertEqual(candidates[0]['url'],URL)
  self.assertTrue(any('disponibilidade' in p for p in candidates[0]['pendencias']))
  product['productData']['is3p']=True
  self.assertEqual(raia.offers(online.SOURCES['raia'],'simeticona',fetch,wanted=profile('G SIMETICONA 40MG 20CP MEDL')),[])
