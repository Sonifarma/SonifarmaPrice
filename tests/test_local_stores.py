from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app import main, local_stores, search_center

ELEMENTS=[
 {'type':'node','id':1,'lat':0.001,'lon':0,'tags':{'name':'Mercado teste','shop':'supermarket','website':'https://loja.example.com/'}},
 {'type':'way','id':2,'center':{'lat':0.002,'lon':0},'tags':{'name':'Farmacia teste','amenity':'pharmacy','brand':'Marca','contact:website':'www.farmacia.example.com'}},
 {'type':'node','id':3,'lat':1,'lon':0,'tags':{'name':'Fora','shop':'cosmetics','website':'https://fora.example.com'}},
 {'type':'node','id':4,'lat':0.003,'lon':0,'tags':{'name':'Sem site','shop':'cosmetics','website':'javascript:alert(1)'}},
]


class StoreRulesTests(unittest.TestCase):
    def test_public_site_only(self):
        for value in ['javascript:alert(1)','http://127.0.0.1/','http://192.168.0.1/','https://localhost/','https://user:pass@example.com/','https://example.com:1234/','https://example.com/a b']:
            self.assertIsNone(local_stores.safe_site(value),value)
        self.assertEqual(local_stores.safe_site('www.example.com'),'https://www.example.com/')

    def test_radius_groups_sites_and_conservative_pharmacy_classification(self):
        result=local_stores.normalize(ELEMENTS+ELEMENTS,{'latitude':0,'longitude':0},2,main.km,{})
        self.assertEqual(len(result),3)
        self.assertEqual(result[0]['grupo'],'supermercados')
        pharmacy=next(row for row in result if row['fonte_id']=='way/2')
        self.assertIsNone(pharmacy['grupo'])
        self.assertTrue(pharmacy['revisao_necessaria'])
        self.assertTrue(pharmacy['site'].startswith('https://'))
        self.assertIsNone(next(row for row in result if row['fonte_id']=='node/4')['site'])
        fixed=local_stores.normalize(ELEMENTS,{'latitude':0,'longitude':0},2,main.km,{'way/2':'farmacias_redes'})
        self.assertTrue(next(row for row in fixed if row['fonte_id']=='way/2')['grupo_confirmado'])

    def test_source_partial_response_is_rejected(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"elements":[],"remark":"timeout"}'
        with patch.object(local_stores,'urlopen',return_value=response):
            with self.assertRaises(ValueError):local_stores.overpass({'latitude':0,'longitude':0},2)


class StoreApiTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'market.sqlite3'
        for p in [patch.object(main,'LOCAL_DB',self.path),patch.object(local_stores,'last_search',float('-inf')),patch.object(local_stores,'overpass',return_value=ELEMENTS)]:
            p.start();self.addCleanup(p.stop)
        self.client=TestClient(main.app);self.addCleanup(self.client.close)
        self.headers={'X-Price-Config':'1'}
        with search_center.database(self.path) as con:
            con.execute('INSERT INTO centro_pesquisa VALUES(1,?,?,?,?,?)',('Endereco ficticio',0,0,1,search_center.now()))

    def search(self,radius=2):
        return self.client.post('/api/mercado/lojas/buscar',headers=self.headers,json={'raio':radius,'centro_versao':1})

    def test_discovery_cache_correction_and_audit(self):
        response=self.search();self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(len(response.json()['lojas']),3)
        self.assertFalse(response.json()['cache'])
        response=self.client.put('/api/mercado/lojas/way/2/grupo',headers=self.headers,json={'grupo':'farmacias_independentes','motivo':'Conferido pelo operador'})
        self.assertEqual(response.status_code,200)
        with patch.object(local_stores,'overpass',side_effect=AssertionError('cache nao deve acessar rede')):
            cached=self.search().json()
        self.assertTrue(cached['cache'])
        self.assertEqual(next(row for row in cached['lojas'] if row['fonte_id']=='way/2')['grupo'],'farmacias_independentes')
        with local_stores.database(self.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM lojas_auditoria').fetchone()[0],1)
        self.assertEqual(self.search(3).status_code,429)

    def test_source_failure_logged_no_invented_store_and_stale_center(self):
        with patch.object(local_stores,'overpass',side_effect=TimeoutError()),self.assertLogs(local_stores.log,level='ERROR'):
            response=self.search()
        self.assertEqual(response.status_code,502)
        self.assertNotIn('lojas',response.json())
        with local_stores.database(self.path) as con:
            self.assertEqual(con.execute('SELECT estado FROM lojas_buscas').fetchone()[0],'falha')
        response=self.client.post('/api/mercado/lojas/buscar',headers=self.headers,json={'raio':2,'centro_versao':2})
        self.assertEqual(response.status_code,409)


class ProductDetailTests(unittest.TestCase):
    def test_demo_detail_keeps_erp_groups_distinct(self):
        rows=[{'produto_id':1,'embalagem_id':11,'descricao':'Produto teste','ean':'4006381333931','classificacoes':[{'id':7,'nome':'Categoria ERP'}],'grupo_remarcacao':{'id':8,'nome':'Grupo ERP'}}]
        with patch.dict('os.environ',{'MODE':'demo'}),patch.object(main,'demo_rows',return_value=rows),TestClient(main.app) as client:
            response=client.get('/api/mercado/produtos/11')
            self.assertEqual(response.status_code,200)
            data=response.json();self.assertEqual(data['classificacoes'][0]['nome'],'Categoria ERP')
            self.assertEqual(data['grupo_remarcacao']['nome'],'Grupo ERP')
            self.assertNotIn('farmacias_redes',str(data))
            self.assertEqual(client.get('/api/mercado/produtos/99').status_code,404)

    def test_postgres_optional_groups_and_readonly_connection(self):
        con=MagicMock();cur=con.cursor.return_value.__enter__.return_value
        cur.fetchall.side_effect=[ [('classificacao','id'),('classificacao','nome'),('classificacaoproduto','produtoid'),('classificacaoproduto','classificacaoid'),('gruporemarcacao','id'),('gruporemarcacao','descricao'),('embalagem','gruporemarcacaoid')],[(7,'Grupo classificacao')]]
        cur.description=[(key,) for key in ['produto_id','embalagem_id','descricao','ean','codigo','apresentacao','preco']]
        cur.fetchone.side_effect=[(1,11,'Teste','4006381333931','001','UN',10),(8,'Grupo remarcacao')]
        with patch.dict('os.environ',{'MODE':'postgres'}),patch.object(main,'db',return_value=con),TestClient(main.app) as client:
            data=client.get('/api/mercado/produtos/11').json()
        self.assertTrue(data['classificacao_disponivel']);self.assertEqual(data['grupo_remarcacao']['nome'],'Grupo remarcacao')
        self.assertTrue(all(call.args[0].lstrip().startswith('SELECT') for call in cur.execute.call_args_list))
        con.close.assert_called_once()


if __name__=='__main__':unittest.main()
