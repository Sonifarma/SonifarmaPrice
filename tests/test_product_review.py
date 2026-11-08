import os
import tempfile
from pathlib import Path
from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import main
from app import product_review as review


ROWS = [
    {'status':'A','tipo_preco':'L','ultima_compra':'2026-11-07T18:00:00','produto_id':1,'embalagem_id':11,'codigo':'001','descricao':'Produto A','ean':'4006381333931','apresentacao':'20 unidades','preco':'10','custo':'8','estoque':5,'vendas30':2,'ultima_entrada':'2026-11-07T18:00:00'},
    {'status':'A','tipo_preco':'L','ultima_compra':'2026-11-06T23:59:59','produto_id':2,'embalagem_id':22,'codigo':'002','descricao':'Produto B','ean':'96385074','apresentacao':'10 unidades','preco':'10','custo':'4','estoque':0,'vendas30':1,'ultima_entrada':'2026-11-06T23:59:59'},
    {'status':'A','tipo_preco':'L','ultima_compra':'2026-10-20T08:00:00','produto_id':3,'embalagem_id':33,'codigo':'003','descricao':'Produto C','ean':'04006381333931','preco':'10','custo':None,'estoque':4,'vendas30':0,'ultima_entrada':'2026-10-20T08:00:00'},
    {'status':'A','tipo_preco':'L','ultima_compra':'2026-10-20T08:00:00','produto_id':4,'embalagem_id':44,'codigo':'004','descricao':'Produto D','ean':None,'preco':'0','custo':'5','estoque':1,'vendas30':0,'ultima_entrada':None},
]


class RuleTests(unittest.TestCase):
    def test_margin_boundary_and_missing_values(self):
        self.assertFalse(review.mark({'preco':'10','custo':'7'},Decimal('30'))['revisar'])
        self.assertTrue(review.mark({'preco':'10','custo':'7.01'},Decimal('30'))['revisar'])
        for value in [None,'',0,-1,'NaN','Infinity']:
            self.assertEqual(review.mark({'preco':value,'custo':5},Decimal('30'))['motivo_revisao'],'preco_inconsistente')
            self.assertEqual(review.mark({'preco':10,'custo':value},Decimal('30'))['motivo_revisao'],'custo_inconsistente')

    def test_dates_include_today_and_month_boundaries(self):
        today=date(2026,11,7)
        self.assertEqual(review.interval('7',today=today),(date(2026,11,1),today))
        self.assertEqual(review.interval('mes_anterior',today=today),(date(2026,10,1),date(2026,10,31)))
        self.assertEqual(review.interval('ontem',today=today),(date(2026,11,6),date(2026,11,6)))
        for args in [('intervalo',None,None),('intervalo',date(2026,11,8),today),('invalido',None,None)]:
            with self.assertRaises(HTTPException):review.interval(*args)

    def test_entry_requires_confirmation_and_safe_identifiers(self):
        with patch.dict(os.environ,{'A7_ENTRY_CONFIRMED':'0'},clear=False):
            self.assertIsNone(review.entry_config())
        with patch.dict(os.environ,{'A7_ENTRY_CONFIRMED':'1','A7_ENTRY_SCHEMA':'public;DROP TABLE produto'},clear=False):
            with self.assertRaises(HTTPException):review.entry_config()

    def test_sql_filters_before_pagination_and_parameterizes_search(self):
        query,params=review.build_query(main.SQL,None,None,'produto',"';DROP TABLE produto;--",date(2026,11,1),date(2026,11,7),Decimal('30'),True,True,100,0)
        self.assertNotIn('DROP TABLE',query)
        self.assertIn('NULL::timestamp AS ultima_entrada',query)
        self.assertLess(query.index('ultima_entrada >= %s'),query.index(' LIMIT %s'))
        self.assertIn(date(2026,11,8),params)
        self.assertEqual(params[-2:],(101,0))
        self.assertIn('COUNT(*) OVER()',query)

    def test_entry_metadata_checks_columns_and_date_type(self):
        config=dict(SCHEMA='public',TABLE='entrada',ID_COLUMN='embalagemid',UNIT_COLUMN='unidadeid',DATE_COLUMN='datahora',STATUS_COLUMN='status')
        cursor=MagicMock()
        cursor.fetchall.return_value=[('embalagemid','integer'),('unidadeid','integer'),('datahora','timestamp without time zone'),('status','text')]
        self.assertEqual(review.check_entry_columns(cursor,config),'timestamp without time zone')
        cursor.fetchall.return_value=[('embalagemid','integer')]
        with self.assertRaises(HTTPException):review.check_entry_columns(cursor,config)


class ApiTests(unittest.TestCase):
    def setUp(self):
        for p in [patch.dict(os.environ,{'MODE':'demo','A7_ENTRY_CONFIRMED':'0'}),patch.object(main,'demo_rows',return_value=ROWS),patch.object(main,'db',side_effect=AssertionError('Nenhuma conexao ERP nos testes'))]:
            p.start();self.addCleanup(p.stop)
        self.client=TestClient(main.app);self.addCleanup(self.client.close)

    def test_defaults_show_only_review_and_keep_old_endpoint(self):
        result=self.client.get('/api/revisao/produtos').json()
        self.assertEqual(result['total'],3)
        self.assertEqual({r['produto_id'] for r in result['items']},{1,3,4})
        self.assertFalse(result['write_enabled'])
        self.assertFalse(result['pricing_enabled'])
        self.assertEqual(self.client.get('/api/products').json()['total'],4)

    def test_date_ends_at_end_of_day_and_applies_before_pagination(self):
        url='/api/revisao/produtos?somente_revisar=false&periodo=intervalo&inicio=2026-11-06&fim=2026-11-07&limit=1'
        first=self.client.get(url).json()
        self.assertEqual(first['total'],2)
        self.assertTrue(first['has_more'])
        self.assertEqual(first['items'][0]['produto_id'],1)
        second=self.client.get(url+'&offset=1').json()
        self.assertEqual(second['items'][0]['produto_id'],2)
        self.assertFalse(second['has_more'])

    def test_stock_and_search_modes(self):
        result=self.client.get('/api/revisao/produtos?somente_revisar=false&somente_estoque=true').json()
        self.assertNotIn(2,[r['produto_id'] for r in result['items']])
        result=self.client.get('/api/revisao/produtos?modo=ean&q=96385074&somente_revisar=false').json()
        self.assertEqual(result['items'][0]['produto_id'],2)
        result=self.client.get('/api/revisao/produtos?modo=codigo&q=001').json()
        self.assertEqual(result['items'][0]['produto_id'],1)

    def test_invalid_dates_and_unmapped_entry_do_not_use_cost_date(self):
        self.assertEqual(self.client.get('/api/revisao/produtos?periodo=intervalo&inicio=2026-11-08&fim=2026-11-07').status_code,422)
        with patch.object(main,'demo_rows',return_value=[dict(ROWS[0],ultima_entrada=None,datahoraconsiderada='2026-11-07')]):
            self.assertFalse(self.client.get('/api/revisao/opcoes').json()['ultima_entrada_disponivel'])
            self.assertEqual(self.client.get('/api/revisao/produtos?periodo=7').status_code,422)
            self.assertIsNone(self.client.get('/api/revisao/produtos').json()['items'][0]['ultima_entrada'])

    def test_postgres_connection_closes_and_nonfinite_values_do_not_escape(self):
        con=MagicMock()
        cursor=con.cursor.return_value.__enter__.return_value
        keys=['produto_id','descricao','preco','custo','embalagem_id','ultima_entrada','total_filtrado']
        cursor.description=[(key,) for key in keys]
        cursor.fetchall.return_value=[(1,'Produto teste',Decimal('10'),Decimal('NaN'),11,None,1)]
        with patch.dict(os.environ,{'MODE':'postgres'}),patch.object(main,'db',return_value=con):
            response=self.client.get('/api/revisao/produtos')
        self.assertEqual(response.status_code,200,response.text)
        self.assertIsNone(response.json()['items'][0]['custo'])
        self.assertEqual(response.json()['items'][0]['motivo_revisao'],'custo_inconsistente')
        con.close.assert_called_once()

    def test_market_lookup_finds_middle_of_description_and_exact_ean(self):
        with patch.object(main,'demo_rows',return_value=[dict(ROWS[0],descricao='DORFLEX COMPRIMIDOS 30 UN'),dict(ROWS[1],descricao='AMOXICILINA 500 MG')]):
            result=self.client.get('/api/mercado/produtos?q=flex').json()
            self.assertEqual(result['items'][0]['descricao'],'DORFLEX COMPRIMIDOS 30 UN')
            self.assertEqual(result['items'][0]['ean'],'4006381333931')
            self.assertEqual(len(self.client.get('/api/mercado/produtos?q=96385074').json()['items']),1)
            self.assertEqual(self.client.get('/api/mercado/produtos?q=xyz').json()['items'],[])
            self.assertEqual(self.client.get('/api/mercado/produtos?q=%20%20').status_code,422)

    def test_market_lookup_paginates_without_price_or_review_filter(self):
        result=self.client.get('/api/mercado/produtos?q=Produto&limit=1&offset=1').json()
        self.assertEqual(result['items'][0]['produto_id'],2)
        self.assertTrue(result['has_more'])
        self.assertNotIn('custo',result['items'][0])
        self.assertNotIn('preco',result['items'][0])

    def test_input_limits_and_web_assets(self):
        for query in ['margem_minima=100','modo=composicao','limit=201','offset=-1','q='+'x'*121]:
            self.assertEqual(self.client.get('/api/revisao/produtos?'+query).status_code,422)
        for path in ['/','/static/app.js','/static/sonifarma-theme.css','/static/sonifarma-logo.png','/static/modelo_precos.csv']:
            self.assertEqual(self.client.get(path).status_code,200)


class MarketScopeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p=patch.object(main,'LOCAL_DB',Path(tmp.name)/'mercado.sqlite3')
        p.start();self.addCleanup(p.stop)
        self.client=TestClient(main.app);self.addCleanup(self.client.close)
        con=main.localdb()
        try:
            for name,lat in [('Perto',0),('Longe',40)]:
                con.execute('INSERT INTO observacoes(ean,grupo,estabelecimento,latitude,longitude,preco,coletado_em,fonte,condicao) VALUES(?,?,?,?,?,?,?,?,?)',
                            ('4006381333931','supermercados',name,lat,0,12,date.today().isoformat(),'teste','Normal'))
            con.commit()
        finally:
            con.close()

    def test_without_coordinates_includes_all_locations(self):
        response=self.client.get('/api/mercado/comparar?ean=4006381333931')
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertEqual(len(data['observacoes']),2)
        self.assertFalse(data['filtro_geografico'])
        self.assertIsNone(data['raio_km'])
        self.assertTrue(all(item['distancia_km'] is None for item in data['observacoes']))

    def test_existing_radius_api_still_works_and_requires_coordinate_pair(self):
        data=self.client.get('/api/mercado/comparar?ean=4006381333931&latitude=0&longitude=0&raio=2').json()
        self.assertEqual(len(data['observacoes']),1)
        self.assertTrue(data['filtro_geografico'])
        self.assertEqual(data['observacoes'][0]['estabelecimento'],'Perto')
        self.assertEqual(self.client.get('/api/mercado/comparar?ean=4006381333931&latitude=0').status_code,422)


if __name__=='__main__':unittest.main()
