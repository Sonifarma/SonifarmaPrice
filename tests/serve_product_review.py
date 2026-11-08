"""Servidor de desenvolvimento com dados ficticios para o teste de navegador."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['MODE'] = 'demo'
from app import main, search_center, local_stores, competitors, online_prices
import uvicorn


def run():
    spec = importlib.util.spec_from_file_location('review_fixtures', ROOT / 'tests' / 'test_product_review.py')
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    rows = [dict(row) for row in fixtures.ROWS]
    rows.extend(dict(fixtures.ROWS[0], produto_id=100+i, embalagem_id=1000+i,
                     descricao='Produto de teste ' + str(i).zfill(3), codigo=str(100+i)) for i in range(110))
    rows[4]['descricao'] = '=HYPERLINK("https://example.invalid")'
    rows[5]['descricao'] = 'Produto <img src=x onerror=alert(1)>'
    rows[0]['classificacoes']=[{'id':7,'nome':'Linha demonstrativa'}]
    rows[0]['grupo_remarcacao']={'id':8,'nome':'Remarcacao demonstrativa'}
    main.demo_rows = lambda: rows
    local_stores.overpass = lambda center,radius: [
        {'type':'node','id':1,'lat':0.001,'lon':0,'tags':{'name':'Mercado ficticio','shop':'supermarket','website':'https://loja.example.com'}},
        {'type':'way','id':2,'center':{'lat':0.002,'lon':0},'tags':{'name':'Farmacia ficticia','amenity':'pharmacy','website':'https://farmacia.example.com'}},
        {'type':'node','id':3,'lat':1,'lon':0,'tags':{'name':'Fora do raio','shop':'cosmetics','website':'https://fora.example.com'}},
    ]
    competitors.fetch_cnpj = lambda cnpj: {'cnpj':cnpj,'razao_social':'Empresa ficticia para teste',
        'descricao_situacao_cadastral':'ATIVA','cnae_fiscal':4711302,'cnae_fiscal_descricao':'Supermercados',
        'logradouro':'Rua de teste','numero':'10','municipio':'Cidade de teste','uf':'SP',
        'consultado_em':competitors.now(),'fonte':'Fonte ficticia de teste'}
    online_prices.SOURCES['drogal']['nomes'].add('FARMACIA FICTICIA')
    online_prices.catalog = lambda source,ean: [{'ean':ean,'produto':'Produto online ficticio',
        'preco':12.34,'moeda':'BRL','url':'https://www.drogal.com.br/produto-ficticio/p',
        'vendedor':'Drogal','condicao':'Preco de teste do catalogo, filial nao confirmada',
        'abrangencia':'site_da_rede','filial_confirmada':False}]
    def description_fixture(source,wanted):
        title='Simeticona 40mg Medley 20 Comprimidos'
        match=online_prices.compare(wanted,title,'Medley')
        if match is None:return []
        offer={'ean':'7896422522823','produto':title,'preco':17.89,'moeda':'BRL',
            'url':'https://www.drogal.com.br/simeticona-ficticia/p','vendedor':'Drogal',
            'condicao':'Preco ficticio para teste','abrangencia':'site_da_rede','filial_confirmada':False}
        return [{'ean':offer['ean'],'produto':title,'marca':'Medley','url':offer['url'],'oferta':offer,**match}]
    online_prices.description_catalog=description_fixture
    # Geocodificador ficticio: o teste de navegador nao acessa servico externo.
    search_center.geocode = lambda address: [{'endereco':'Rua demonstrativa, 10, Cidade de teste, Brasil','latitude':0.0,'longitude':0.0,'tipo':'house'}]
    with tempfile.TemporaryDirectory() as directory:
        main.LOCAL_DB = Path(directory) / 'mercado.sqlite3'
        uvicorn.run(main.app, host='127.0.0.1', port=18770)


if __name__ == '__main__':
    run()
