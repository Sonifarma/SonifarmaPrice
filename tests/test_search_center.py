from pathlib import Path
from datetime import date
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app import main
from app import search_center as center

CANDIDATE={'endereco':'Rua de teste, 10, Cidade ficticia, Brasil','latitude':0.0,'longitude':0.0,'tipo':'house'}


class CenterTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'mercado.sqlite3'
        for p in [patch.object(main,'LOCAL_DB',self.path),patch.object(center,'last_lookup',float('-inf')),patch.object(center,'geocode',return_value=[CANDIDATE]),patch.dict('os.environ',{'MODE':'demo'})]:
            p.start();self.addCleanup(p.stop)
        self.client=TestClient(main.app);self.addCleanup(self.client.close)
        self.headers={'X-Price-Config':'1'}

    def search(self):
        response=self.client.post('/api/mercado/centro/buscar',json={'endereco':'Rua de teste, 10, Cidade ficticia, Brasil'},headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['candidatos'][0]['candidato_id']

    def save(self,token,version=0):
        return self.client.put('/api/mercado/centro',headers=self.headers,json={'candidato_id':token,'versao':version})

    def test_requires_explicit_confirmation_and_persists_shared_center(self):
        self.assertIsNone(self.client.get('/api/mercado/centro').json()['centro'])
        token=self.search()
        self.assertIsNone(self.client.get('/api/mercado/centro').json()['centro'])
        response=self.save(token)
        self.assertEqual(response.status_code,200,response.text)
        saved=response.json()['centro']
        self.assertEqual(saved['endereco'],CANDIDATE['endereco'])
        self.assertEqual(saved['versao'],1)
        self.assertEqual(self.client.get('/api/mercado/centro').json()['centro']['versao'],1)
        with center.database(self.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM centro_auditoria').fetchone()[0],1)
        self.assertEqual(self.save(token,0).status_code,409)
        self.assertEqual(self.save('a'*32).status_code,422)

    def test_cache_and_rate_limit(self):
        token=self.search()
        with patch.object(center,'geocode',side_effect=AssertionError('Nao consultar fonte para cache')):
            self.assertEqual(self.search(),token)
        response=self.client.post('/api/mercado/centro/buscar',headers=self.headers,json={'endereco':'Outro endereco, 12, Outra cidade'})
        self.assertEqual(response.status_code,429)

    def test_source_failure_keeps_previous_center_and_origin_guard(self):
        self.save(self.search())
        with patch.object(center,'last_lookup',float('-inf')),patch.object(center,'geocode',side_effect=TimeoutError()),self.assertLogs(center.log,level='ERROR'):
            response=self.client.post('/api/mercado/centro/buscar',headers=self.headers,json={'endereco':'Outro endereco, 12, Outra cidade'})
        self.assertEqual(response.status_code,502)
        self.assertEqual(self.client.get('/api/mercado/centro').json()['centro']['versao'],1)
        self.assertEqual(self.client.post('/api/mercado/centro/buscar',json={'endereco':'Rua de teste, 10'}).status_code,403)
        self.assertEqual(self.client.post('/api/mercado/centro/buscar',headers=dict(self.headers,Origin='https://outro.invalid'),json={'endereco':'Rua de teste, 10'}).status_code,403)

    def test_radius_uses_saved_point_and_rejects_missing_or_stale_center(self):
        query='/api/mercado/comparar?ean=4006381333931&usar_centro=true&raio=2'
        self.assertEqual(self.client.get(query).status_code,422)
        self.save(self.search())
        con=main.localdb()
        try:
            for name,lat in [('Perto',0.001),('Longe',1)]:
                con.execute('INSERT INTO observacoes(ean,grupo,estabelecimento,latitude,longitude,preco,coletado_em,fonte,condicao) VALUES(?,?,?,?,?,?,?,?,?)',
                            ('4006381333931','supermercados',name,lat,0,12,date.today().isoformat(),'fixture','Normal'))
            con.commit()
        finally:con.close()
        response=self.client.get(query+'&centro_versao=1')
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual([r['estabelecimento'] for r in data['observacoes']],['Perto'])
        self.assertEqual(data['centro']['endereco'],CANDIDATE['endereco'])
        self.assertTrue(data['filtro_geografico'])
        self.assertEqual(self.client.get(query+'&centro_versao=2').status_code,409)
        self.assertEqual(self.client.get(query+'&latitude=0&longitude=0').status_code,422)



class GeocoderTests(unittest.TestCase):
    def test_source_bounds_and_fixed_endpoint(self):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=b'[{"lat":"NaN","lon":"0","display_name":"invalid"},{"lat":"0","lon":"0","display_name":"valid","type":"house"}]'
        with patch.object(center,'urlopen',return_value=response) as open_url:
            result=center.geocode('Rua de teste, 10')
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['latitude'],0)
        self.assertTrue(open_url.call_args.args[0].full_url.startswith('https://nominatim.openstreetmap.org/search?'))
        self.assertEqual(open_url.call_args.kwargs['timeout'],20)


if __name__=='__main__':unittest.main()
