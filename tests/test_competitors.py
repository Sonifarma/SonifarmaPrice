from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from fastapi.testclient import TestClient
from app import competitors as c,main,local_stores as stores
from test_local_stores import ELEMENTS

class CompetitorsTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'db.sqlite3'
        self.rows=stores.normalize(ELEMENTS,{'latitude':0,'longitude':0},2,main.km,{})
        c.register(self.path,self.rows,c.now())

    def test_checksum_and_country_prefix(self):
        self.assertEqual(c.normalize_cnpj('00.000.000/0001-91'),'00000000000191')
        self.assertEqual(c.normalize_cnpj('BR00000000000191'),'00000000000191')
        for value in ['00000000000000','00000000000192','<script>',None]:self.assertIsNone(c.normalize_cnpj(value))

    def test_idempotence_radius_and_confirmed_group_survive_refresh(self):
        self.assertEqual(c.register(self.path,self.rows,c.now()),{'adicionados':0,'atualizados':0,'cnpjs_identificados':0})
        c.set_group(self.path,'way/2','farmacias_redes')
        c.register(self.path,self.rows,c.now())
        result=c.within_radius(self.path,{'latitude':0,'longitude':0},.25,main.km)
        self.assertEqual(len(result),2)
        self.assertEqual(result[1]['grupo'],'farmacias_redes')
        with c.database(self.path) as con:self.assertEqual(con.execute('SELECT count(*) FROM concorrentes_cadastro').fetchone()[0],3)

    def test_explicit_identity_only_and_no_merge_by_cnpj(self):
        self.assertTrue(all(row['cnpj'] is None for row in c.within_radius(self.path,{'latitude':0,'longitude':0},2,main.km)))
        self.rows[0]['cnpj']=self.rows[1]['cnpj']='00000000000191'
        c.register(self.path,self.rows,c.now())
        with c.database(self.path) as con:self.assertEqual(con.execute('SELECT count(*) FROM concorrentes_cadastro WHERE cnpj IS NOT NULL').fetchone()[0],2)

    def test_enrichment_cache_failure_preserves_last_success(self):
        self.rows[0]['cnpj']='00000000000191';c.register(self.path,self.rows,c.now())
        with c.database(self.path) as con:identifier=con.execute("SELECT id FROM concorrentes_cadastro WHERE cnpj IS NOT NULL").fetchone()[0]
        info={'fonte':'Teste','consultado_em':c.now(),'razao_social':'Empresa teste'}
        with patch.object(c,'last_cnpj',float('-inf')),patch.object(c,'fetch_cnpj',return_value=info) as source:
            c.enrich(self.path,identifier);c.enrich(self.path,identifier);self.assertEqual(source.call_count,1)
        with c.database(self.path) as con:con.execute("UPDATE concorrentes_cadastro SET cnpj_consultado_em='2000-01-01'")
        with patch.object(c,'last_cnpj',float('-inf')),patch.object(c,'fetch_cnpj',side_effect=OSError('offline')):
            with self.assertRaises(Exception):c.enrich(self.path,identifier)
        with c.database(self.path) as con:
            row=con.execute('SELECT * FROM concorrentes_cadastro WHERE id=?',(identifier,)).fetchone()
            self.assertEqual(json.loads(row['dados_cnpj']),info)
            self.assertEqual(row['cnpj_consultado_em'],'2000-01-01')
            self.assertEqual(row['cnpj_status'],'falha_consulta')

    def test_whitelist_and_response_identity(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'cnpj':'00000000000191','qsa':[{'cpf':'private'}],'razao_social':'Teste'}).encode()
        with patch.object(c,'urlopen',return_value=response):
            data=c.fetch_cnpj('00000000000191');self.assertNotIn('qsa',data)
            with self.assertRaises(ValueError):c.fetch_cnpj('11222333000181')

    def test_search_automatically_registers_and_directory_has_scope_guard(self):
        from app import search_center
        with patch.object(main,'LOCAL_DB',self.path),patch.object(stores,'overpass',return_value=ELEMENTS),patch.object(stores,'last_search',float('-inf')),patch.object(search_center,'get_center',return_value={'latitude':0,'longitude':0,'versao':1,'endereco':'Teste'}),patch.object(stores,'get_center',return_value={'latitude':0,'longitude':0,'versao':1,'endereco':'Teste'}),patch.object(c,'get_center',return_value={'latitude':0,'longitude':0,'versao':1,'endereco':'Teste'}):
            with TestClient(main.app) as client:
                res=client.post('/api/mercado/lojas/buscar',json={'raio':2,'centro_versao':1},headers={'X-Price-Config':'1'})
                self.assertEqual(res.status_code,200,res.text)
                self.assertEqual(client.get('/api/concorrentes?raio=2&centro_versao=1&limit=1').json()['total'],3)
                self.assertEqual(client.get('/api/concorrentes?raio=2&centro_versao=2').status_code,409)
                self.assertEqual(client.post('/api/concorrentes/1/cnpj',json={'cnpj':'00000000000191'}).status_code,403)

class IdentifiedBranchesTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'db.sqlite3'

    def test_researched_list_validates_branch_payloads_and_existing_user_rows(self):
        from app.identified_competitors import IDENTIFIED
        self.assertEqual(len(IDENTIFIED),11)
        rows=[]
        for i,entry in enumerate(IDENTIFIED):
            self.assertEqual(c.normalize_cnpj(entry['cnpj']),entry['cnpj'])
            self.assertEqual(entry['dados']['cnpj'],entry['cnpj'])
            self.assertEqual(entry['dados']['numero'],entry['numero'])
            self.assertIn(entry['rua'],c.normalized(entry['dados']['logradouro']))
            self.assertNotIn('qsa',entry['dados'])
            rows.append({'fonte_id':entry['fonte_id'] or 'node/'+str(200+i),'nome':entry['nomes'][0],
                         'latitude':-22.753,'longitude':-47.36,'endereco':'Rua '+entry['rua']+' '+entry['numero'],'grupo':None,'site':None})
        result=c.register(self.path,rows,c.now())
        self.assertEqual(result['cnpjs_identificados'],11)
        self.assertEqual(c.apply_identified(self.path),0)
        with c.database(self.path) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM concorrentes_cadastro WHERE dados_cnpj IS NOT NULL').fetchone()[0],11)
            self.assertEqual(con.execute("SELECT count(*) FROM concorrentes_auditoria WHERE acao='filial_identificada_por_endereco'").fetchone()[0],11)

    def test_missing_number_requires_reviewed_source_id_and_wrong_branch_never_matches(self):
        from app.identified_competitors import IDENTIFIED
        entry=next(e for e in IDENTIFIED if e['cnpj']=='03476811029214')
        row={'fonte_id':entry['fonte_id'],'nome':'Dia','endereco':'Rua Iacanga','latitude':-22.753,'longitude':-47.36}
        self.assertTrue(c.identified_match(row,entry))
        self.assertFalse(c.identified_match(dict(row,fonte_id='way/999'),entry))
        self.assertFalse(c.identified_match(dict(row,nome='Outra loja'),entry))
        self.assertFalse(c.identified_match(dict(row,latitude=0),entry))
        drogal=IDENTIFIED[0]
        base=dict(row,nome='Drogal',endereco='Rua Iacanga 1786')
        self.assertFalse(c.identified_match(base,drogal))
        self.assertFalse(c.identified_match(dict(base,endereco='Rua Limeira 786'),drogal))
        self.assertFalse(c.identified_match(dict(base,endereco='Rua Iacanga'),drogal))

    def test_previous_cnpj_and_classification_are_preserved(self):
        row={'fonte_id':'node/123','nome':'Drogal','endereco':'Rua Iacanga 786','latitude':-22.753,'longitude':-47.36,
             'cnpj':'00000000000191','grupo':'farmacias_redes','grupo_confirmado':True}
        c.register(self.path,[row],c.now())
        self.assertEqual(c.apply_identified(self.path),0)
        with c.database(self.path) as con:
            stored=con.execute('SELECT * FROM concorrentes_cadastro').fetchone()
            self.assertEqual(stored['cnpj'],'00000000000191')
            self.assertEqual(stored['grupo'],'farmacias_redes')
            self.assertEqual(stored['latitude'],row['latitude'])

    def test_upgrade_fills_existing_rows_on_listing_without_external_service(self):
        row={'fonte_id':'node/123','nome':'Drogal','endereco':'Rua Iacanga 786','latitude':-22.753,'longitude':-47.36}
        with patch.object(c,'apply_identified',return_value=0):c.register(self.path,[row],c.now())
        center={'latitude':-22.753,'longitude':-47.36,'versao':1,'endereco':'Centro teste'}
        with patch.object(main,'LOCAL_DB',self.path),patch.object(c,'get_center',return_value=center),patch.object(c,'fetch_cnpj',side_effect=AssertionError('Rede nao deve ser usada')):
            with TestClient(main.app) as client:
                data=client.get('/api/concorrentes?raio=2&centro_versao=1').json()
                self.assertEqual(data['cnpjs_preenchidos'],1)
                self.assertEqual(data['items'][0]['cnpj'],'54375647008454')
                self.assertEqual(data['items'][0]['dados_cnpj']['numero'],'786')
                self.assertEqual(client.get('/api/concorrentes?raio=2&centro_versao=1').json()['cnpjs_preenchidos'],0)
