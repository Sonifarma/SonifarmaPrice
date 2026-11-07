import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from pydantic import ValidationError
from app import discovery as d
from app import main as main


class FakeConnector:
    def __init__(self, elements=None, fail=False):
        self.calls = []
        self.elements = elements if elements is not None else [
            {'type': 'node', 'id': 1, 'lat': 0, 'lon': 0.01, 'tags': {'name': 'Mercado teste', 'shop': 'supermarket'}},
            {'type': 'node', 'id': 2, 'lat': 0, 'lon': 0.03, 'tags': {'name': 'Farmacia teste', 'amenity': 'pharmacy', 'brand': 'Marca'}},
        ]
        self.fail = fail

    def discover(self, lat, lon, radius):
        self.calls.append(radius)
        if self.fail:
            raise TimeoutError('simulated source failure')
        return self.elements


class DiscoveryTests(unittest.TestCase):
    def params(self, **kwargs):
        return d.Search(latitude=0, longitude=0, coordenadas_confirmadas=True, **kwargs)

    def test_coordinates_and_radii_validation(self):
        for kwargs in [dict(coordenadas_confirmadas=False), dict(latitude=float('nan')), dict(raios_km=[2, 1]), dict(raios_km=[2, 11]), dict(raios_km=[2, 2])]:
            values = dict(latitude=0, longitude=0, coordenadas_confirmadas=True)
            values.update(kwargs)
            with self.assertRaises(ValidationError):
                d.Search(**values)

    def test_expansion_distance_and_deduplication(self):
        source = FakeConnector()
        result = d.search(self.params(), source)
        self.assertEqual(source.calls, [2, 3, 5, 8, 10])
        self.assertEqual(len(result['estabelecimentos']), 2)
        self.assertEqual(result['validos'], 1)
        pharmacy = next(x for x in result['estabelecimentos'] if x['fonte_id'] == 'node/2')
        self.assertIsNone(pharmacy['grupo'])
        self.assertTrue(pharmacy['revisao_necessaria'])
        self.assertAlmostEqual(result['estabelecimentos'][0]['distancia_km'], 1.112, places=3)

    def test_early_stop_on_target(self):
        source = FakeConnector()
        result = d.search(self.params(quantidade=1), source)
        self.assertTrue(result['meta_atingida'])
        self.assertEqual(source.calls, [2])

    def test_correction_and_block(self):
        result = d.search(self.params(), FakeConnector(), {
            'node/1': {'bloqueado': True},
            'node/2': {'grupo': 'farmacias_redes', 'bloqueado': False},
        })
        self.assertEqual(result['validos'], 1)
        pharmacy = next(x for x in result['estabelecimentos'] if x['fonte_id'] == 'node/2')
        self.assertFalse(pharmacy['revisao_necessaria'])
        self.assertEqual(pharmacy['grupo'], 'farmacias_redes')

    def test_failure_has_no_invented_results(self):
        with self.assertLogs(d.logger, level='ERROR'):
            result = d.search(self.params(), FakeConnector(fail=True))
        self.assertEqual(result['estado'], 'parcial')
        self.assertEqual(result['estabelecimentos'], [])
        self.assertEqual(len(result['falhas']), 1)

    def test_partial_preserves_previous_radius(self):
        class Partial(FakeConnector):
            def discover(self, lat, lon, radius):
                if radius > 2:
                    raise TimeoutError()
                return super().discover(lat, lon, radius)
        with self.assertLogs(d.logger, level='ERROR'):
            result = d.search(self.params(), Partial())
        self.assertEqual(result['estado'], 'parcial')
        self.assertEqual(len(result['estabelecimentos']), 1)
        self.assertFalse(result['meta_atingida'])

    def test_outside_radius_and_bad_coordinates_excluded(self):
        source = FakeConnector(elements=[
            {'type': 'node', 'id': 1, 'lat': 90, 'lon': 90, 'tags': {'name': 'Fora', 'shop': 'supermarket'}},
            {'type': 'node', 'id': 2, 'lat': float('nan'), 'lon': 0, 'tags': {'name': 'Invalido', 'shop': 'supermarket'}},
        ])
        self.assertEqual(d.search(self.params(), source)['validos'], 0)


class ConnectorTests(unittest.TestCase):
    def test_fixed_endpoint_encoded_query_and_timeout(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"elements": []}'
        with patch.object(d, 'urlopen', return_value=response) as open_url:
            self.assertEqual(d.OverpassConnector().discover(0, 0, 2), [])
        req = open_url.call_args.args[0]
        self.assertEqual(req.full_url, 'https://overpass-api.de/api/interpreter')
        self.assertEqual(open_url.call_args.kwargs['timeout'], 30)
        from urllib.parse import parse_qs
        query = parse_qs(req.data.decode())['data'][0]
        self.assertIn('around:2000,0,0', query)
        self.assertNotIn('area', query)
        self.assertIn('out center tags', query)

    def test_partial_or_oversized_source_response_rejected(self):
        for raw in [b'{"elements": [], "remark": "timeout"}', b'x' * 5_000_001]:
            response = MagicMock()
            response.__enter__.return_value.read.return_value = raw
            with patch.object(d, 'urlopen', return_value=response):
                with self.assertRaises(ValueError):
                    d.OverpassConnector().discover(0, 0, 2)


class ApiTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / 'market.sqlite3'
        for patcher in [patch.object(d, 'DB_PATH', self.db), patch.object(main, 'LOCAL_DB', self.db),
                        patch.object(d, 'last_request', 0), patch.object(d, 'connector', FakeConnector()),
                        patch.object(main, 'demo_rows', return_value=[{'descricao': 'Produto teste', 'ean': '7891058002916', 'codigo': '1'}, {'descricao': 'Segundo produto', 'ean': '7891058002916', 'codigo': '2'}]),
                        patch.dict(os.environ, {'MODE': 'demo', 'PRICE_ADMIN_TOKEN': 'test-only-token'})]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {'X-Price-Token': 'test-only-token'}
        self.body = dict(latitude=0, longitude=0, coordenadas_confirmadas=True, quantidade=1)

    def test_authentication_and_disabled_default(self):
        self.assertEqual(self.client.post('/api/descoberta/pesquisar', json=self.body).status_code, 401)
        with patch.dict(os.environ, {'PRICE_ADMIN_TOKEN': ''}):
            self.assertEqual(self.client.get('/api/descoberta/historico', headers=self.headers).status_code, 503)
        self.assertFalse(self.db.exists())

    def test_search_history_rate_limit_and_audit(self):
        r = self.client.post('/api/descoberta/pesquisar', json=self.body, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['validos'], 1)
        history = self.client.get('/api/descoberta/historico', headers=self.headers).json()['execucoes']
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['parametros']['latitude'], 0)
        self.assertEqual(self.client.post('/api/descoberta/pesquisar', json=self.body, headers=self.headers).status_code, 429)
        response = self.client.put('/api/descoberta/fontes/node/1', headers=self.headers,
                                   json={'grupo': 'perfumarias', 'bloqueado': True, 'motivo': 'teste de revisao'})
        self.assertEqual(response.status_code, 200)
        with d.connect() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM descoberta_auditoria').fetchone()[0], 1)
        # Historico da execucao anterior nao e reescrito por uma correcao.
        history = self.client.get('/api/descoberta/historico', headers=self.headers).json()['execucoes']
        self.assertFalse(history[0]['resultado']['estabelecimentos'][0]['bloqueado'])

    def test_source_failure_stored_and_existing_api_keeps_working(self):
        with patch.object(d, 'connector', FakeConnector(fail=True)), self.assertLogs(d.logger, level='ERROR'):
            result = self.client.post('/api/descoberta/pesquisar', headers=self.headers, json=self.body)
        self.assertEqual(result.status_code, 502)
        self.assertIn('execucao_id', result.json())
        self.assertEqual(self.client.get('/api/status').status_code, 200)
        self.assertEqual(self.client.get('/api/products?limit=1').status_code, 200)

    def test_v11_demo_csv_compare_and_atomic_rejection(self):
        for path in ['/', '/api/status', '/api/diagnostic', '/api/mercado/status', '/static/discovery.js']:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        status = self.client.get('/api/status').json()
        self.assertFalse(status['write_enabled'])
        self.assertFalse(status['pricing_enabled'])
        page = self.client.get('/api/products?limit=1&offset=1').json()
        self.assertEqual(len(page['items']), 1)
        from datetime import date
        header = 'ean;grupo;estabelecimento;latitude;longitude;preco;coletado_em;fonte;condicao\n'
        row = f'7891058002916;supermercados;Teste;0;0;12.00;{date.today().isoformat()};teste;normal\n'
        response = self.client.post('/api/mercado/importar', files={'arquivo': ('test.csv', header + row)})
        self.assertEqual(response.status_code, 200, response.text)
        bad = self.client.post('/api/mercado/importar', files={'arquivo': ('test.csv', header + row + row.replace('12.00', '-1'))})
        self.assertEqual(bad.status_code, 400)
        result = self.client.get('/api/mercado/comparar?ean=7891058002916&latitude=0&longitude=0').json()
        self.assertEqual(len(result['observacoes']), 1)
        self.assertEqual(result['menor_preco'], 12)

    def test_postgres_options_remain_read_only(self):
        with patch('psycopg2.connect') as connect:
            main.db()
        self.assertIn('default_transaction_read_only=on', connect.call_args.kwargs['options'])
        self.assertIn('statement_timeout=12000', connect.call_args.kwargs['options'])


if __name__ == '__main__':
    unittest.main()
