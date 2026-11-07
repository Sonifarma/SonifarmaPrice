"""Servidor de desenvolvimento com dados ficticios para o teste de navegador."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['MODE'] = 'demo'
from app import main
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
    with tempfile.TemporaryDirectory() as directory:
        main.LOCAL_DB = Path(directory) / 'mercado.sqlite3'
        uvicorn.run(main.app, host='127.0.0.1', port=18770)


if __name__ == '__main__':
    run()
