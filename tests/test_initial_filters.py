import copy,os,unittest
from datetime import date
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import main,product_review as review
import test_product_review as fixtures

class PeriodTests(unittest.TestCase):
 def test_requested_presets_and_calendar_months(self):
  day=date(2026,11,8)
  expected={'hoje':(day,day),'ontem':(date(2026,11,7),date(2026,11,7)),'ate_hoje':(None,day),
   'semana':(date(2026,11,2),day),'semana_anterior':(date(2026,10,26),date(2026,11,1)),
   'mes_completo':(date(2026,11,1),date(2026,11,30)),'mes':(date(2026,11,1),day),
   'mes_anterior':(date(2026,10,1),date(2026,10,31)),'45':(date(2026,9,25),day),
   '3meses':(date(2026,8,8),day),'6meses':(date(2026,5,8),day),'12meses':(date(2025,11,8),day)}
  for preset,range_ in expected.items():self.assertEqual(review.interval(preset,today=day),range_,preset)
  self.assertEqual(review.months_before(date(2026,5,31),3),date(2026,2,28))
  self.assertEqual(review.months_before(date(2024,2,29),12),date(2023,2,28))

class PurchaseMappingTests(unittest.TestCase):
 def test_purchase_mapping_never_inherits_entry_confirmation(self):
  with patch.dict(os.environ,{'A7_ENTRY_CONFIRMED':'1','A7_PURCHASE_CONFIRMED':'0'}):
   self.assertIsNone(review.entry_config('A7_PURCHASE_'))

 def test_fiscal_mapping_requires_explicit_semantics(self):
  settings={'A7_PURCHASE_SOURCE':'notafiscal','A7_PURCHASE_CONFIRMED':'0'}
  with patch.dict(os.environ,settings,clear=True):self.assertIsNone(review.purchase_config())
  settings.update(A7_PURCHASE_CONFIRMED='1',A7_PURCHASE_STATUS_VALUE='VALIDA_TESTE',A7_PURCHASE_MOVEMENT_VALUE='ENTRADA_TESTE',A7_PURCHASE_CFOPS='5102, 6102')
  with patch.dict(os.environ,settings,clear=True):
   config=review.purchase_config();self.assertEqual(config['CFOPS'],['5102','6102'])
  with patch.dict(os.environ,{},clear=True):
   config=review.purchase_config()
   self.assertEqual(config['STATUS_VALUE'],'C');self.assertEqual(config['MOVEMENT_VALUE'],'A')
   self.assertIn('5102',config['CFOPS']);self.assertNotIn('5929',config['CFOPS'])
   self.assertNotIn('5202',config['CFOPS']);self.assertNotIn('5152',config['CFOPS'])
  with patch.dict(os.environ,dict(settings,A7_PURCHASE_CFOPS="5102');DROP TABLE nota;--"),clear=True):
   with self.assertRaises(review.HTTPException):review.purchase_config()

 def test_fiscal_schema_is_validated_before_query(self):
  from unittest.mock import Mock
  metadata=[[(n,'timestamp without time zone' if n=='datahoraentrada' else 'text') for n in ['id','unidadenegocioid','fornecedorid','datahoraentrada','status','tipomovimentacaofisica']],
   [(n,'boolean' if n in {'bonificacao','itemsemmovimentacao'} else 'numeric') for n in ['notafiscalid','embalagemid','quantidade','bonificacao','itemsemmovimentacao','cfop']],
   [('id','bigint'),('produtoid','bigint')]]
  cursor=Mock();cursor.fetchall.side_effect=metadata
  config=dict(SOURCE='notafiscal',SCHEMA='public')
  self.assertEqual(review.check_purchase_columns(cursor,config),'timestamp without time zone')
  cursor.fetchall.side_effect=[metadata[0],[]]
  with self.assertRaises(review.HTTPException):review.check_purchase_columns(cursor,config)
  cursor.fetchall.side_effect=[[(n,'text') for n,_ in metadata[0]],metadata[1],metadata[2]]
  with self.assertRaises(review.HTTPException):review.check_purchase_columns(cursor,config)

class InitialFiltersApiTests(unittest.TestCase):
 def setUp(self):
  self.rows=copy.deepcopy(fixtures.ROWS)
  self.rows[1].update(tipo_preco='M')
  self.rows[2].update(status='I')
  self.rows[3].update(ultima_compra='2020-01-01',ultima_entrada='2026-11-07')
  for item in [patch.dict(os.environ,{'MODE':'demo'}),patch.object(main,'demo_rows',side_effect=lambda:self.rows)]:item.start();self.addCleanup(item.stop)
  self.client=TestClient(main.app);self.addCleanup(self.client.close)
 def test_default_active_released_and_explicit_filters(self):
  data=self.client.get('/api/revisao/produtos?somente_revisar=false').json()
  self.assertEqual({r['produto_id'] for r in data['items']},{1,4})
  self.assertEqual(self.client.get('/api/revisao/produtos?tipo_preco=monitorado&somente_revisar=false').json()['items'][0]['produto_id'],2)
  self.assertEqual(self.client.get('/api/revisao/produtos?status_produto=inativo').json()['items'][0]['produto_id'],3)
  self.assertEqual(self.client.get('/api/revisao/produtos?tipo_preco=todos&status_produto=todos&somente_revisar=false').json()['total'],4)
 def test_purchase_filter_does_not_use_entry_or_cost_date(self):
  data=self.client.get('/api/revisao/produtos?data_filtro=compra&periodo=intervalo&inicio=2026-11-01&fim=2026-11-08&somente_revisar=false').json()
  self.assertEqual([r['produto_id'] for r in data['items']],[1])
  self.rows=[dict(self.rows[0],ultima_compra=None,datahoraconsiderada='2026-11-07')]
  response=self.client.get('/api/revisao/produtos?data_filtro=compra&periodo=45')
  self.assertEqual(response.status_code,422)
  self.assertFalse(self.client.get('/api/revisao/opcoes').json()['ultima_compra_disponivel'])
 def test_filters_and_total_apply_before_offset(self):
  self.rows=[dict(self.rows[0],produto_id=n,embalagem_id=n,status='I' if n%2 else 'A',tipo_preco='M' if n%3 else 'L') for n in range(1,301)]
  first=self.client.get('/api/revisao/produtos?somente_revisar=false&limit=10').json()
  second=self.client.get('/api/revisao/produtos?somente_revisar=false&limit=10&offset=10').json()
  self.assertEqual(first['total'],50);self.assertEqual(second['total'],50)
  self.assertFalse({r['embalagem_id'] for r in first['items']} & {r['embalagem_id'] for r in second['items']})
  self.assertTrue(first['has_more'])
 def test_invalid_filter_values_are_rejected(self):
  for params in ['tipo_preco=x','status_produto=x','data_filtro=x']:
   self.assertEqual(self.client.get('/api/revisao/produtos?'+params).status_code,422)
