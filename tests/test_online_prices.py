import copy,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import main,online_prices as online,competitors,search_center

EAN='7891058002916'
def catalog_fixture(host='www.drogal.com.br',seller='Drogal'):
 return [{'productName':'Produto teste','link':'https://'+host+'/produto/p','items':[{'itemId':'123','ean':EAN,'sellers':[{'sellerId':'1','sellerName':seller,'commertialOffer':{'Price':12.34,'AvailableQuantity':99999,'IsAvailable':True}}]}]}]

class ParsingTests(unittest.TestCase):
 def test_exact_ean_only_and_no_marketplace_or_invalid_price(self):
  source=online.SOURCES['drogal'];data=catalog_fixture()
  self.assertEqual(online.parse_offers(data,source,EAN)[0]['preco'],12.34)
  self.assertEqual(online.parse_offers(data,source,'0000000000000'),[])
  for field,value in [('Price',0),('Price',.001),('Price',True),('Price',float('inf')),('AvailableQuantity',0),('IsAvailable',False),('CurrencyCode','USD')]:
   changed=copy.deepcopy(data);changed[0]['items'][0]['sellers'][0]['commertialOffer'][field]=value
   self.assertEqual(online.parse_offers(changed,source,EAN),[],(field,value))
  for field,value in [('sellerId','99'),('sellerName','Outro vendedor')]:
   changed=copy.deepcopy(data);changed[0]['items'][0]['sellers'][0][field]=value
   self.assertEqual(online.parse_offers(changed,source,EAN),[])

 def test_conditional_offers_are_labeled_and_duplicate_skus_not_counted_twice(self):
  data=catalog_fixture();data[0]['items'][0]['sellers'][0]['commertialOffer']['Teasers']=[{'name':'Compre 3'}]
  result=online.parse_offers(data+data,online.SOURCES['drogal'],EAN)
  self.assertEqual(len(result),1)
  self.assertIn('condicionadas',result[0]['condicao'])
  self.assertFalse(result[0]['filial_confirmada'])
  self.assertNotIn('AvailableQuantity',result[0])

 def test_links_and_redirects_stay_on_registered_https_host(self):
  for url in ['http://www.drogal.com.br/p','https://127.0.0.1/p','https://www.drogal.com.br.evil.test/p','https://user@www.drogal.com.br/p','javascript:alert(1)','https://www.drogal.com.br:123/p']:
   self.assertIsNone(online.public_link(url,'www.drogal.com.br'))
  with self.assertRaises(ValueError):online.SameHostRedirect('www.drogal.com.br').redirect_request(None,None,302,'',{},'https://example.com/')

 def test_robots_denial_stops_catalog_request(self):
  with patch.dict(online.robots_cache,{},clear=True),patch.object(online,'fetch_bytes',return_value=b'User-agent: *\nDisallow: /api/') as fetch:
   with self.assertRaises(ValueError):online.catalog(online.SOURCES['drogal'],EAN)
   self.assertEqual(fetch.call_count,1)

class OnlineApiTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.path=Path(tmp.name)/'data.sqlite3'
  p=patch.object(main,'LOCAL_DB',self.path);p.start();self.addCleanup(p.stop)
  with search_center.database(self.path) as con:con.execute('INSERT INTO centro_pesquisa VALUES(1,?,?,?,?,?)',('Centro ficticio',0,0,1,search_center.now()))
  competitors.register(self.path,[{'fonte_id':'node/1','nome':'Drogal','latitude':.001,'longitude':0,'endereco':'Rua teste 1'},
   {'fonte_id':'node/2','nome':'Drogal','latitude':.002,'longitude':0,'endereco':'Rua teste 2'},
   {'fonte_id':'node/3','nome':'Drogaria São Paulo','latitude':.003,'longitude':0,'endereco':'Rua teste 3'},
   {'fonte_id':'node/4','nome':'Tenda','latitude':.004,'longitude':0,'endereco':'Rua teste 4'},
   {'fonte_id':'node/5','nome':'Drogal','latitude':1,'longitude':0,'endereco':'Fora do raio'}],competitors.now())
  self.client=TestClient(main.app);self.addCleanup(self.client.close)
 def request(self,**overrides):
  return self.client.post('/api/mercado/online/consultar',json=dict({'ean':EAN,'raio':2,'centro_versao':1},**overrides),headers={'X-Price-Config':'1'})
 def provider(self,source,ean):
  return online.parse_offers(catalog_fixture(source['host'],source['nome']),source,ean)
 def test_one_query_per_network_filters_radius_and_keeps_online_prices_out_of_local_observations(self):
  with patch.object(online,'catalog',side_effect=self.provider) as fetch:
   response=self.request();self.assertEqual(response.status_code,200,response.text);data=response.json()
   self.assertEqual(fetch.call_count,2)
   self.assertEqual(len(data['fontes'][0]['lojas_no_raio']),2)
   self.assertEqual(len(data['fontes'][0]['ofertas']),1)
   self.assertEqual(data['sem_integracao'],['Tenda'])
   again=self.request().json();self.assertTrue(again['fontes'][0]['cache']);self.assertEqual(fetch.call_count,2)
  with online.database(self.path) as con:
   self.assertEqual(con.execute("SELECT count(*) FROM sqlite_master WHERE name='observacoes'").fetchone()[0],0)
   stored=con.execute('SELECT ofertas FROM catalogos_online').fetchone()[0]
   self.assertNotIn('PriceToken',stored)
 def test_failure_preserves_previous_values_and_collection_time_without_false_freshness(self):
  with patch.object(online,'catalog',side_effect=self.provider):self.request()
  with online.database(self.path) as con:con.execute("UPDATE catalogos_online SET coletado_em='2000-01-01T00:00:00+00:00'")
  with patch.object(online,'catalog',side_effect=TimeoutError()):data=self.request().json()
  for source in data['fontes']:
   self.assertEqual(source['estado'],'indisponivel');self.assertTrue(source['desatualizado'])
   self.assertEqual(source['coletado_em'],'2000-01-01T00:00:00+00:00');self.assertEqual(source['ofertas'][0]['preco'],12.34)
 def test_partial_failure_reports_each_source_without_inventing_prices(self):
  def partial(source,ean):
   if source['nome']=='Drogal':raise TimeoutError()
   return self.provider(source,ean)
  with patch.object(online,'catalog',side_effect=partial):data=self.request().json()
  self.assertEqual(data['fontes'][0]['ofertas'],[])
  self.assertEqual(data['fontes'][0]['estado'],'indisponivel')
  self.assertEqual(data['fontes'][1]['estado'],'consultado')
 def test_invalid_scope_or_ean_never_calls_provider(self):
  with patch.object(online,'catalog',side_effect=AssertionError('Nao deve consultar')):
   self.assertEqual(self.request(centro_versao=2).status_code,409)
   self.assertEqual(self.request(ean='produto').status_code,422)
   self.assertEqual(self.client.post('/api/mercado/online/consultar',json={'ean':EAN,'raio':2,'centro_versao':1}).status_code,403)
   with search_center.database(self.path) as con:con.execute('DELETE FROM centro_pesquisa')
   self.assertEqual(self.request().status_code,422)

 def test_todo_dia_uses_browser_adapter_and_shared_radius_registry(self):
  competitors.register(self.path,[{'fonte_id':'node/11','nome':'Drogaria Todo Dia','latitude':.001,'longitude':0,'endereco':'Rua teste'},
    {'fonte_id':'node/12','nome':'Droga Todo Dia','latitude':.002,'longitude':0,'endereco':'Avenida teste'},
    {'fonte_id':'node/13','nome':'Drogaria Tododia','latitude':1,'longitude':0,'endereco':'Fora do raio'}],competitors.now())
  offer=dict(ean=EAN,produto='Produto Todo Dia',preco=9.1,url='https://www.drogariatododia.com/produto-p123',condicao='Preco publico')
  with patch.object(online,'catalog',side_effect=self.provider) as fetch,patch.object(online.todo_dia,'lookup',return_value=[offer]) as browser:data=self.request().json()
  self.assertEqual(fetch.call_count,2);self.assertEqual(browser.call_count,1)
  manual=next(r for r in data['fontes'] if r['fonte']=='tododia')
  self.assertEqual(manual['estado'],'consultado')
  self.assertEqual(manual['ofertas'][0]['preco'],9.1)
  self.assertIsNotNone(manual['coletado_em'])
  self.assertEqual(len(manual['lojas_no_raio']),2)
  self.assertNotIn('url_consulta',manual)
  with online.database(self.path) as con:self.assertEqual(con.execute("SELECT count(*) FROM catalogos_online WHERE fonte='tododia'").fetchone()[0],1)

 def test_groups_follow_shared_registry_without_duplicating_network_offer(self):
  competitors.set_group(self.path,'node/1','farmacias_redes')
  competitors.set_group(self.path,'node/2','farmacias_redes')
  with patch.object(online,'catalog',side_effect=self.provider):data=self.request().json()
  self.assertEqual(data['fontes'][0]['grupo'],'farmacias_redes')
  self.assertEqual(len(data['fontes'][0]['ofertas']),1)
  competitors.set_group(self.path,'node/2','farmacias_independentes')
  with patch.object(online,'catalog',side_effect=AssertionError('cache')):data=self.request().json()
  self.assertIsNone(data['fontes'][0]['grupo'])
