import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app import composition as comp,online_prices as online
from test_online_prices import catalog_fixture

TITLE='Simeticona 40mg 20 comprimidos Medley'

class CompositionTests(unittest.TestCase):
 def test_brands_are_not_guessed_and_presentation_is_required(self):
  ref=comp.signature('G SIMETICONA 40MG 20CP MEDL')
  self.assertEqual(ref,comp.signature(TITLE))
  for title in ['Simeticona 125mg 20 comprimidos','Simeticona 40mg 10 comprimidos','Simeticona 40mg 20 capsulas']:
   self.assertNotEqual(ref,comp.signature(title))
  for title in ['Luftal 40mg 20 comprimidos','20 BI 30CAP MOME','Simeticona 40mg','Simeticona + Alverina 40mg 20 comprimidos','Amoxicilina Clavulanato 500mg 20 comprimidos']:
   self.assertIsNone(comp.signature(title))
  self.assertEqual(comp.signature('Marca comercial 40mg 20 comprimidos','SIMETICONA'),ref)
 def test_concentration_volume_route_and_release_do_not_mix(self):
  ref=comp.signature('Simeticona 75mg/ml gotas 15ml')
  for title in ['Simeticona 75mg gotas 15ml','Simeticona 75mg/ml gotas 10ml','Simeticona 75mg/ml solucao 15ml']:
   self.assertNotEqual(ref,comp.signature(title))
  self.assertNotEqual(comp.signature(TITLE),comp.signature(TITLE+' liberacao prolongada'))
 def test_catalog_accepts_other_makers_but_rejects_mismatches_unavailable_and_duplicate_eans(self):
  ref=comp.signature(TITLE);products=[]
  for i,(title,brand) in enumerate([(TITLE,'Medley'),('Simeticona 40mg 20 comprimidos EMS','EMS'),('Simeticona 40mg 10 comprimidos Cimed','Cimed'),('Simeticona 125mg 20 comprimidos','EMS'),('Simeticona 40mg 20 capsulas','EMS')]):
   product=catalog_fixture()[0];product.update(productName=title,brand=brand)
   product['items'][0].update(ean=str(7890000000000+i),name=title)
   products.append(product)
  invalid=copy.deepcopy(products[0]);invalid['Princípio Ativo']=['Simeticona + Alverina'];invalid['items'][0]['ean']='7890000000099';products.append(invalid)
  products.append(copy.deepcopy(products[0]))
  with patch.object(online,'catalog_data',return_value=products) as fetch:
   offers=online.composition_catalog(online.SOURCES['drogal'],ref)
  self.assertEqual([o['laboratorio'] for o in offers],['Medley','EMS'])
  self.assertNotIn('medley',fetch.call_args.args[1].lower())
  products[0]['items'][0]['name']='Simeticona 40mg 10 comprimidos'
  with patch.object(online,'catalog_data',return_value=products[:1]):
   self.assertEqual(online.composition_catalog(online.SOURCES['drogal'],ref),[])
 def test_exact_ean_metadata_conflict_does_not_choose_arbitrary_composition(self):
  one=comp.signature(TITLE);two=comp.signature('Simeticona 125mg 20 comprimidos')
  self.assertIsNone(comp.reference(TITLE,[{'ofertas':[{'ean':'123','composicao':one},{'ean':'123','composicao':two}]}],'123'))
 def test_cache_failure_keeps_original_collection_time_and_data(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'market.sqlite3';ref=comp.signature(TITLE)
   with patch.object(online,'composition_catalog',return_value=[{'ean':'7890000000000','preco':10}]):
    first=online.query_composition(path,'drogal',ref)
   with patch.object(online,'composition_catalog',side_effect=AssertionError('cache')):
    self.assertEqual(online.query_composition(path,'drogal',ref)['estado'],'cache')
   with online.database(path) as con:con.execute("UPDATE catalogos_descricao SET coletado_em='2000-01-01'")
   with patch.object(online,'composition_catalog',side_effect=TimeoutError()):stale=online.query_composition(path,'drogal',ref)
   self.assertTrue(stale['desatualizado']);self.assertEqual(stale['coletado_em'],'2000-01-01')
   self.assertEqual(stale['ofertas'],first['ofertas'])
 def test_scope_only_integrated_networks_in_radius_and_one_offer_per_sku(self):
  source=dict(fonte='drogal',rede='Drogal',grupo='farmacias_redes',ofertas=[])
  offer=dict(ean='7890000000000',preco=10)
  with patch.object(online,'query_composition',return_value=dict(ofertas=[offer,offer],estado='consultado',coletado_em='2026-11-08',desatualizado=False)) as query:
   data=online.composition_results(None,TITLE,None,[source,dict(source,fonte='tododia')])
  self.assertEqual(query.call_count,1);self.assertEqual(len(data['ofertas']),1)
