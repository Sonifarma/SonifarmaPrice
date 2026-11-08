import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app import main,diagnostico_precos as diag,search_center,competitors

class PriceDiagnosticTests(unittest.TestCase):
 def test_diagnostic_separates_local_store_selection_from_public_catalog_without_erp(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'local.sqlite3'
   with search_center.database(path) as con:con.execute('INSERT INTO centro_pesquisa VALUES(1,?,?,?,?,?)',('Centro ficticio',0,0,1,search_center.now()))
   offers=[{'ean':'7896230304536','preco':14.99,'produto':'Produto ficticio','url':'https://www.drogaraia.com.br/teste.html'}]
   with patch.object(main,'LOCAL_DB',path),patch.object(main,'db',side_effect=AssertionError('Nao consultar ERP')),patch.object(diag.online,'catalog',return_value=offers):
    report=diag.report('7896230304536',2)
    self.assertEqual(report['raias_reconhecidas_no_raio'],[]);self.assertEqual(report['catalogo_raia'],'consultado')
    self.assertIn('nao identificada',report['orientacao'])
    competitors.register(path,[{'fonte_id':'node/1','nome':'Droga Raia','latitude':.001,'longitude':0,'endereco':'Endereco ficticio'}],competitors.now())
    report=diag.report('7896230304536',2)
    self.assertEqual(len(report['raias_reconhecidas_no_raio']),1)
    self.assertEqual(report['ofertas_teste'][0]['preco'],14.99)
