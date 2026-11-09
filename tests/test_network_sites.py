import tempfile
import unittest
from pathlib import Path
from app import competitors as c,main

class NetworkSiteTests(unittest.TestCase):
    def test_missing_sites_and_aliases(self):
        for name,url in [('Drogal','https://www.drogal.com.br/'),('Farmácia Drogal','https://www.drogal.com.br/'),('Tenda Atacado','https://www.tendaatacado.com.br/'),('Atacado Higa','https://www.higa.com.br/'),('HIGA ATACADO','https://www.higa.com.br/')]:
            result=c.complement_site({'nome':name,'site':None})
            self.assertEqual(result['site'],url)
            self.assertEqual(result['site_abrangencia'],'rede')
            self.assertEqual(result['site_origem'],'informado_pelo_operador')

    def test_existing_sites_and_unrelated_names(self):
        item={'nome':'Drogal','site':'https://filial.example/'}
        self.assertEqual(c.complement_site(dict(item)),item)
        for name in ['Drogaleste','Tenda de Eventos','Drogaria Higa Outra Empresa','Outro Atacado']:
            item={'nome':name,'site':None};self.assertEqual(c.complement_site(dict(item)),item)

    def test_shared_saved_directory_and_radius(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'local.sqlite3'
            rows=[{'nome':name,'fonte_id':'node/'+str(i),'latitude':0,'longitude':lon,'endereco':'Rua teste','site':None} for i,(name,lon) in enumerate([('Drogal',.001),('Tenda Atacado',.002),('Atacado Higa',.003),('Higa',1)],1)]
            c.register(path,rows,c.now())
            for _ in range(2):
                result=c.within_radius(path,{'latitude':0,'longitude':0},2,main.km)
                self.assertEqual(len(result),3)
                self.assertEqual([r['site'] for r in result],['https://www.drogal.com.br/','https://www.tendaatacado.com.br/','https://www.higa.com.br/'])
            with c.database(path) as con:self.assertEqual(con.execute('SELECT count(*) FROM concorrentes_cadastro').fetchone()[0],4)
