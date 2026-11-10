import unittest
from unittest.mock import patch,MagicMock
from app import diagnostico_produto as diagnostic

CONFIG=dict(STATUS_VALUE='C',MOVEMENT_VALUE='A',CFOPS=['1102'])

class DiagnosticTests(unittest.TestCase):
 def row(self):return dict(unidade=1,status='C',movimento='A',tem_fornecedor=True,entrada='2026-11-06',quantidade=2,bonificacao=False,sem_movimento=False,cfop='1102')
 def test_completed_purchase_on_sixth_is_not_rejected(self):
  self.assertEqual(diagnostic.exclusion_reasons(self.row(),CONFIG,1),[])
 def test_every_purchase_gate_is_explained_including_null_flags(self):
  for key,value in [('unidade',2),('status','I'),('movimento','R'),('tem_fornecedor',False),('entrada',None),('quantidade',0),('bonificacao',True),('bonificacao',None),('sem_movimento',True),('sem_movimento',None),('cfop','9999')]:
   row=self.row();row[key]=value
   self.assertEqual(len(diagnostic.exclusion_reasons(row,CONFIG,1)),1,(key,value))
 def test_demo_and_invalid_ean_do_not_connect_to_erp(self):
  with patch.object(diagnostic.server,'db',side_effect=AssertionError('Nao conectar')):
   with self.assertRaises(ValueError):diagnostic.diagnose('invalid')
   with patch.object(diagnostic.server,'mode',return_value='demo'):
    with self.assertRaises(ValueError):diagnostic.diagnose('7891000071625')
 def test_missing_ean_is_reported_without_querying_invoices(self):
  con=MagicMock();cur=con.cursor.return_value.__enter__.return_value
  cur.description=[('produto_id',)];cur.fetchall.return_value=[]
  with patch.object(diagnostic.server,'mode',return_value='postgres'),patch.object(diagnostic.server,'db',return_value=con):
   result=diagnostic.diagnose('7891000071625')
  self.assertIn('nao encontrado',result['conclusao']);self.assertEqual(cur.execute.call_count,1)
  self.assertEqual(cur.execute.call_args.args[1],('7891000071625',))
  con.close.assert_called_once()
 def test_found_product_compares_name_and_explains_rejected_invoice(self):
  con=MagicMock();cur=con.cursor.return_value.__enter__.return_value
  entries=[{'produto_id':123,'codigo':'12','descricao':'NAN COMFOR 1','status':'A','tipo_preco':'L','embalagem_id':34,'ean':'7891000071625','apresentacao':'800 G'},
           {'produto_id':123,'embalagem_id':34,'ean':'7891000071625','ultima_compra':None},
           dict(self.row(),status='I')]
  def execute(sql,params):
   row=entries.pop(0);cur.description=[(k,) for k in row];cur.fetchall.return_value=[tuple(row.values())]
  cur.execute.side_effect=execute
  config=dict(CONFIG,SOURCE='notafiscal',SCHEMA='public')
  with patch.object(diagnostic.server,'mode',return_value='postgres'),patch.object(diagnostic.server,'db',return_value=con),patch.object(diagnostic.review,'purchase_config',return_value=config),patch.object(diagnostic.review,'check_purchase_columns',return_value='timestamp without time zone'):
   result=diagnostic.diagnose('7891000071625','LEITE NAN COMFORT 1 800G')
  self.assertFalse(result['cadastros'][0]['corresponde_texto_digitado'])
  self.assertFalse(result['compras_recentes'][0]['aceita_pela_regra_compra'])
  self.assertIn('Status',result['compras_recentes'][0]['motivos_exclusao'][0])
  self.assertIsNone(result['ultima_compra_reconhecida'][0]['ultima_compra'])
  self.assertEqual(cur.execute.call_count,3)
