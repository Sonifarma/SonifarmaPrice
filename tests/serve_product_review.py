"""Servidor de desenvolvimento com dados ficticios para o teste de navegador."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['MODE'] = 'demo'
from app import main, search_center
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
    main.demo_rows = lambda: rows
    # Geocodificador ficticio: o teste de navegador nao acessa servico externo.
    search_center.geocode = lambda address: [{'endereco':'Rua demonstrativa, 10, Cidade de teste, Brasil','latitude':0.0,'longitude':0.0,'tipo':'house'}]
    with tempfile.TemporaryDirectory() as directory:
        main.LOCAL_DB = Path(directory) / 'mercado.sqlite3'
        uvicorn.run(main.app, host='127.0.0.1', port=18770)


if __name__ == '__main__':
    run()
