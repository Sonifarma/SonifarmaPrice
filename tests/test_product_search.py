import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app.product_search import profile,compare
from app import online_prices as online
import test_online_prices as online_fixtures
catalog_fixture=online_fixtures.catalog_fixture
EAN=online_fixtures.EAN

class NormalizationTests(unittest.TestCase):
 def test_three_requested_descriptions(self):
  p=profile('20 BI 30CAP MOME');self.assertEqual(p['descricao'],'20 BI 30 CAPSULAS MOMENTA');self.assertEqual(p['quantidade'],30)
  self.assertIsNotNone(compare(p,'Probiótico 20 bi 30 cápsulas','Eurofarma'))
  p=profile('FRD GERIA COTIDIAN CLAS G C/7');self.assertEqual(p['quantidade'],7);self.assertEqual(p['tamanho'],'G')
  self.assertIn('7 UNIDADES',p['descricao']);self.assertIsNotNone(compare(p,'Fralda Adulto Cotidian Clássica G Com 7 Unids','Cotidian'))
  p=profile('G SIMETICONA 40MG 20CP MEDL');self.assertEqual(p['doses'],['40MG']);self.assertEqual(p['fabricante'],'MEDLEY');self.assertEqual(p['forma'],'COMPRIMIDOS');self.assertTrue(p['generico'])
  self.assertIsNotNone(compare(p,'Antigases Simeticona 40mg Genérico Medley 20 Comprimidos','Medley'))
 def test_dose_pack_form_size_and_manufacturer_conflicts_are_rejected(self):
  p=profile('G SIMETICONA 40MG 20CP MEDL')
  for title,brand in [('Simeticona 75mg/ml Medley 15ml Gotas','Medley'),('Simeticona 40mg Medley 4 Comprimidos','Medley'),('Simeticona 40mg Cimed 20 Comprimidos','Cimed'),('Luftal Simeticona 40mg 20 Comprimidos','Luftal'),('Omeprazol 40mg Medley 20 Comprimidos','Medley')]:
   self.assertIsNone(compare(p,title,brand),title)
  p=profile('FRD GERIA COTIDIAN CLAS G C/7')
  for title in ['Fralda Cotidian Clássica XG 7 Unidades','Fralda Cotidian Clássica G 21 Unidades','Fralda Cotidian Plus G 7 Unidades','Protetor de Cama Cotidian 7 Unidades']:
   self.assertIsNone(compare(p,title,'Cotidian'),title)
  self.assertIsNone(compare(profile('20 BI 30CAP MOME'),'20 Bi 10 Cápsulas','20 Bi'))
  self.assertIsNone(compare(profile('20 BI 30CAP MOME'),'20 Bi Cimed 30 Cápsulas','Cimed'))
 def test_missing_attributes_are_explicit_not_inferred(self):
  result=compare(profile('G SIMETICONA 40MG 20CP MEDL'),'Simeticona Medley','Medley')
  self.assertTrue(result['pendencias']);self.assertNotIn('Dosagem confere',result['conferencias'])
 def test_sku_variant_cannot_borrow_package_size_from_product_title(self):
  data=catalog_fixture();data[0].update(productName='20 Bi 30 Cápsulas',brand='20 Bi');data[0]['items'][0]['name']='20 Bi 10 Cápsulas'
  with patch.object(online,'catalog_data',return_value=data):self.assertEqual(online.description_catalog(online.SOURCES['drogal'],profile('20 BI 30CAP MOME')),[])

class DescriptionApiTests(unittest.TestCase):
 setUp=online_fixtures.OnlineApiTests.setUp
 request=online_fixtures.OnlineApiTests.request
 provider=online_fixtures.OnlineApiTests.provider
 def candidate_provider(self,source,wanted):
  offer=self.provider(source,EAN)[0]
  return [{'ean':EAN,'produto':'Simeticona 40mg Medley 20 Comprimidos','marca':'Medley','url':offer['url'],
   'oferta':offer,'pendencias':[],'conferencias':['Dosagem confere','Quantidade confere'],'pontuacao':20}]
 def test_description_only_finds_candidates_but_does_not_graph_them_until_selected(self):
  body={'ean':None,'descricao':'G SIMETICONA 40MG 20CP MEDL'}
  with patch.object(online,'description_catalog',side_effect=self.candidate_provider) as fetch:
   data=self.request(**body).json()
   self.assertEqual(len(data['fontes'][0]['candidatos']),1);self.assertEqual(data['fontes'][0]['ofertas'],[])
   self.assertIn('MEDLEY',data['busca_normalizada']);self.assertTrue(data['links_pesquisa'])
   confirmed=self.request(**body,selecoes={'drogal':EAN}).json()
   self.assertEqual(fetch.call_count,2) # once per source; confirmation uses description cache
  offer=confirmed['fontes'][0]['ofertas'][0]
  self.assertEqual(offer['ean'],EAN);self.assertEqual(offer['correspondencia'],'descricao_confirmada')
  self.assertFalse(offer['filial_confirmada'])
 def test_same_ean_found_by_text_is_confirmed_without_choosing_different_item(self):
  with patch.object(online,'catalog',return_value=[]),patch.object(online,'description_catalog',side_effect=self.candidate_provider):
   data=self.request(descricao='G SIMETICONA 40MG 20CP MEDL').json()
  self.assertEqual(data['fontes'][0]['estado'],'ean_por_descricao')
  self.assertEqual(data['fontes'][0]['ofertas'][0]['ean'],EAN)
 def test_forged_selection_is_not_accepted_as_a_match(self):
  with patch.object(online,'description_catalog',side_effect=self.candidate_provider):
   data=self.request(ean=None,descricao='G SIMETICONA 40MG 20CP MEDL',selecoes={'drogal':'0000000000000'}).json()
  self.assertEqual(data['fontes'][0]['ofertas'],[])
 def test_candidate_failures_do_not_relabel_old_collection_as_current(self):
  body={'ean':None,'descricao':'G SIMETICONA 40MG 20CP MEDL'}
  with patch.object(online,'description_catalog',side_effect=self.candidate_provider):self.request(**body)
  with online.database(self.path) as con:con.execute("UPDATE catalogos_descricao SET coletado_em='2000-01-01T00:00:00+00:00'")
  with patch.object(online,'description_catalog',side_effect=TimeoutError()):data=self.request(**body,selecoes={'drogal':EAN}).json()
  self.assertTrue(data['fontes'][0]['desatualizado']);self.assertEqual(data['fontes'][0]['coletado_em'],'2000-01-01T00:00:00+00:00')
