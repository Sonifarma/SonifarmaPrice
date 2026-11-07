"""Provas locais de bibliotecas candidatas. Sem ERP, internet ou dados de producao."""
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from threading import Event
import unittest

from price_parser import Price
from stdnum import ean
import extruct
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
import networkx as nx
import osmnx as ox
from openpyxl import Workbook
from cmed_probe import inspect_workbook


class PriceTests(unittest.TestCase):
    def test_brl_cents(self):
        p = Price.fromstring('R$ 12,90', decimal_separator=',')
        self.assertEqual(p.amount, Decimal('12.90'))
        self.assertEqual(p.currency, 'R$')

    def test_brl_thousands(self):
        self.assertEqual(Price.fromstring('R$ 1.234,56', decimal_separator=',').amount, Decimal('1234.56'))

    def test_absent_price_and_percentage(self):
        for value in ['Indisponivel', '50% OFF', 'R$']:
            self.assertIsNone(Price.fromstring(value).amount)

    def test_free_is_zero_and_must_be_rejected_by_business_rules(self):
        self.assertEqual(Price.fromstring('Free').amount, Decimal('0'))

    def test_multiple_prices_require_context(self):
        # Limite observado: nao e seguro aplicar a string inteira como oferta.
        self.assertEqual(Price.fromstring('De R$ 19,90 por R$ 12,90', decimal_separator=',').amount, Decimal('19.90'))
        self.assertEqual(Price.fromstring('3x de R$ 12,00', decimal_separator=',').amount, Decimal('3'))


class GtinTests(unittest.TestCase):
    def test_valid_identifier_and_wrong_checksum(self):
        self.assertTrue(ean.is_valid('4006381333931'))
        self.assertFalse(ean.is_valid('4006381333932'))

    def test_ean8_and_zero_prefix_preserved(self):
        self.assertTrue(ean.is_valid('96385074'))
        self.assertTrue(ean.is_valid('04006381333931'))
        self.assertEqual(ean.validate('04006381333931'), '04006381333931')

    def test_junk_does_not_become_product(self):
        for value in ['', '123', 'ABCDEFGHIJKLM']:
            self.assertFalse(ean.is_valid(value))


class ExtractionTests(unittest.TestCase):
    def test_product_offer_jsonld(self):
        product = {'@context': 'https://schema.org', '@type': 'Product', 'name': 'Produto ficticio',
                   'gtin13': '4006381333931', 'offers': {'@type': 'Offer', 'price': '12.90',
                   'priceCurrency': 'BRL', 'availability': 'https://schema.org/InStock',
                   'url': 'https://example.invalid/produto'}}
        html = '<script type="application/ld+json">' + json.dumps(product) + '</script>'
        result = extruct.extract(html, syntaxes=['json-ld'])['json-ld'][0]
        self.assertEqual(result['gtin13'], '4006381333931')
        self.assertEqual(result['offers']['priceCurrency'], 'BRL')
        self.assertEqual(Decimal(result['offers']['price']), Decimal('12.90'))
        self.assertNotIn('storeLocation', result['offers'])  # Oferta online nao confirma preco de filial.

    def test_empty_page_has_no_invented_offer(self):
        self.assertEqual(extruct.extract('<html>Indisponivel</html>', syntaxes=['json-ld'])['json-ld'], [])

    def test_graph_keeps_multiple_offers(self):
        payload = {'@context': 'https://schema.org', '@graph': [
            {'@type': 'Product', 'gtin13': '4006381333931', 'offers': [
                {'@type': 'Offer', 'price': '12.90', 'priceCurrency': 'BRL'},
                {'@type': 'Offer', 'price': '10.90', 'priceCurrency': 'BRL', 'description': 'Clube'}]}]}
        result = extruct.extract('<script type="application/ld+json">'+json.dumps(payload)+'</script>', syntaxes=['json-ld'])
        offers = result['json-ld'][0]['@graph'][0]['offers']
        self.assertEqual(len(offers), 2)
        self.assertEqual(offers[1]['description'], 'Clube')


class SchedulerTests(unittest.TestCase):
    def test_one_off_job_really_executes(self):
        done = Event()
        scheduler = BackgroundScheduler(timezone='America/Sao_Paulo')
        scheduler.add_job(done.set, 'date', max_instances=1)
        scheduler.start()
        try:
            self.assertTrue(done.wait(5), 'Job nao executou em 5 segundos')
        finally:
            scheduler.shutdown(wait=True)

    def test_local_timezone(self):
        trigger = CronTrigger(hour=9, minute=0, timezone='America/Sao_Paulo')
        upcoming = trigger.get_next_fire_time(None, datetime(2026, 11, 7, 11, 0, tzinfo=timezone.utc))
        self.assertEqual(upcoming.hour, 9)
        self.assertEqual(upcoming.astimezone(timezone.utc).hour, 12)

    def test_sqlite_persists_job_between_scheduler_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            url = 'sqlite:///' + str(Path(tmp) / 'jobs.sqlite3')
            scheduler = BackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(url=url)})
            scheduler.start(paused=True)
            try:
                scheduler.add_job(print, 'date', run_date=datetime(2030, 1, 1, tzinfo=timezone.utc),
                                  id='teste-persistencia', args=['job ficticio'], max_instances=1)
            finally:
                scheduler.shutdown()
            restarted = BackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(url=url)})
            restarted.start(paused=True)
            try:
                job = restarted.get_job('teste-persistencia')
                self.assertIsNotNone(job)
                self.assertEqual(job.args, ('job ficticio',))
                self.assertEqual(job.max_instances, 1)
            finally:
                restarted.shutdown()


class GeographyTests(unittest.TestCase):
    def test_distance_in_meters(self):
        self.assertAlmostEqual(ox.distance.great_circle(0, 0, 0, 0.01), 1111.95, delta=1)

    def test_route_can_differ_from_direct_edge(self):
        graph = nx.MultiDiGraph(crs='EPSG:4326')
        graph.add_edge(1, 2, length=100)
        graph.add_edge(2, 3, length=100)
        graph.add_edge(1, 3, length=500)
        self.assertEqual(ox.routing.shortest_path(graph, 1, 3, weight='length'), [1, 2, 3])


class CmedTests(unittest.TestCase):
    def workbook(self, rows):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / 'teste.xlsx'
        book = Workbook()
        for row in rows:
            book.active.append(row)
        book.save(path)
        book.close()
        return path

    def test_dynamic_header_and_pmc_columns(self):
        path = self.workbook([['Nota'], ['Publicada em 07/11/2026'], [],
                              ['SUBSTÂNCIA', 'EAN 1', 'PMC 18%', 'PMC 20%'],
                              ['FICTICIA', '04006381333931', '12,90*', '13,20']])
        result = inspect_workbook(path)
        self.assertEqual(result['linha_cabecalho'], 4)
        self.assertEqual(result['linhas_amostradas'], 1)
        self.assertIn('PMC 18%', result['colunas'])

    def test_cover_sheet_is_not_mistaken_for_data(self):
        path = self.workbook([['Publicada em 09/10/2026'], ['Nota explicativa']])
        book = __import__('openpyxl').load_workbook(path)
        sheet = book.create_sheet('Lista PMC')
        sheet.append(['SUBSTÂNCIA', 'EAN 1', 'PMC 18%'])
        sheet.append(['FICTICIA', '04006381333931', '12,90'])
        book.save(path)
        book.close()
        result = inspect_workbook(path)
        self.assertEqual(result['aba'], 'Lista PMC')
        self.assertIn('Publicada em 09/10/2026', result['notas'])

    def test_pmvg_is_not_pmc(self):
        path = self.workbook([['SUBSTANCIA', 'EAN 1', 'PMVG 18%']])
        with self.assertRaisesRegex(ValueError, 'sem coluna PMC'):
            inspect_workbook(path)

    def test_missing_header_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Cabecalho'):
            inspect_workbook(self.workbook([['Qualquer coisa']]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
