import unittest
from app.product_search import profile,compare
from app.todo_dia import rank_urls

class SalineSearchTests(unittest.TestCase):
 def test_erp_pack_abbreviations_match_public_todo_dia_title(self):
  wanted=profile('SORO FISIOLOGICO C/10 AMP 5ML')
  self.assertEqual(wanted['principais'],['SORO','FISIOLOGICO'])
  self.assertEqual(wanted['quantidade'],10);self.assertEqual(wanted['forma'],'AMPOLAS')
  actual='SORO FISIOLOGICO ADV 10 AMPOLAS C/ 5ML'
  self.assertIsNotNone(compare(wanted,actual,'ADV'))
  found=profile(actual)
  self.assertEqual(found['quantidade'],10);self.assertEqual(found['volumes_ml'],['5'])
  self.assertNotIn('5 UNIDADES',found['descricao'])
  self.assertIsNone(compare(wanted,'SORO FISIOLOGICO ADV 1 AMPOLA 5ML','ADV'))
  self.assertIsNone(compare(wanted,'SORO FISIOLOGICO ADV 10 AMPOLAS 10ML','ADV'))
  self.assertEqual(rank_urls([{'url':'https://www.drogariatododia.com/soro-p1','titulo':actual,'slug':'soro fisiologico adv 10 ampolas com 5 ml'}],wanted),['https://www.drogariatododia.com/soro-p1'])
