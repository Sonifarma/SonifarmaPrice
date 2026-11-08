import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import main,competitors as c,search_center as sc

class ManualTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'local.sqlite3'
        self.patch=patch.object(main,'LOCAL_DB',self.path);self.patch.start();self.addCleanup(self.patch.stop)
        self.client=TestClient(main.app);self.addCleanup(self.client.close)
        with sc.database(self.path) as con:
            con.execute("INSERT INTO centro_pesquisa VALUES(1,'Centro',0,0,1,?)",(sc.now(),))
            con.execute('INSERT INTO centro_candidatos VALUES(?,?,?,?,?,?,?)',('a'*32,'rua exemplo 504 americana','Rua Exemplo 504',0,.001,'building',sc.now()))
        self.body=dict(cnpj='03.340.744/0001-43',nome='Droga Ge',endereco='Rua Exemplo 504 Americana',candidato_id='a'*32,centro_versao=1,raio=2,grupo='farmacias_independentes',site='https://example.org')

    def post(self,**changes):
        return self.client.post('/api/concorrentes/manual',json=self.body|changes,headers={'X-Price-Config':'1'})

    def test_create_shared_radius_audit_duplicate_group(self):
        response=self.post();self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.post().status_code,409)
        items=c.within_radius(self.path,{'latitude':0,'longitude':0},2,main.km)
        self.assertEqual(len(items),1);self.assertEqual(items[0]['cnpj'],'03340744000143')
        self.assertEqual(items[0]['fonte_id'],'manual/'+str(response.json()['id']))
        self.assertNotIn('openstreetmap',items[0]['fonte_url'])
        self.assertEqual(c.within_radius(self.path,{'latitude':1,'longitude':1},2,main.km),[])
        c.set_group(self.path,items[0]['fonte_id'],'farmacias_redes')
        with c.database(self.path) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM concorrentes_auditoria').fetchone()[0],2)
            self.assertEqual(con.execute('SELECT grupo FROM concorrentes_cadastro').fetchone()[0],'farmacias_redes')

    def test_guard_invalid_identity_address_expired_and_radius(self):
        self.assertEqual(self.client.post('/api/concorrentes/manual',json=self.body).status_code,403)
        for change in [dict(cnpj='03.340.744/0001-44'),dict(endereco='Outro endereco'),dict(centro_versao=2),dict(site='javascript:alert(1)'),dict(grupo='invalid')]:
            self.assertIn(self.post(**change).status_code,[409,422])
        with sc.database(self.path) as con:con.execute('UPDATE centro_candidatos SET longitude=1')
        self.assertEqual(self.post().status_code,422)
        with sc.database(self.path) as con:con.execute("UPDATE centro_candidatos SET longitude=0,criado_em='2000-01-01'")
        self.assertEqual(self.post().status_code,422)
        with c.database(self.path) as con:self.assertEqual(con.execute('SELECT count(*) FROM concorrentes_cadastro').fetchone()[0],0)

    def test_lookup_failure_no_partial_registration(self):
        with patch.object(c,'last_cnpj',float('-inf')),patch.object(c,'fetch_cnpj',side_effect=OSError()):
            response=self.client.post('/api/concorrentes/cnpj/buscar',headers={'X-Price-Config':'1'},json={'cnpj':self.body['cnpj']})
        self.assertEqual(response.status_code,502)
        self.assertEqual(c.within_radius(self.path,{'latitude':0,'longitude':0},2,main.km),[])
