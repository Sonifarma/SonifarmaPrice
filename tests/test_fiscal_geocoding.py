import unittest
from unittest.mock import patch
from app import search_center as sc,competitors as c,main
from fastapi.testclient import TestClient

class FiscalGeocodingTests(unittest.TestCase):
    def test_structured_address_fallback(self):
        point={'endereco':'Rua Iacanga, Americana','latitude':-22.7,'longitude':-47.3,'tipo':'house'}
        with patch.object(sc,'geocode_request',side_effect=[[],[point]]) as query,patch.object(sc.time,'sleep'):
            self.assertEqual(sc.geocode('RUA IACANGA, 356, AMERICANA, SP, Brasil'),[point])
        self.assertEqual(query.call_args.args[1]['street'],'356 RUA IACANGA')
        self.assertEqual(query.call_args.args[1]['city'],'AMERICANA')

    def test_road_is_explicitly_approximate_and_never_city_fallback(self):
        point={'endereco':'Rua Iacanga, Americana','latitude':-22.7,'longitude':-47.3,'tipo':'road'}
        with patch.object(sc,'geocode_request',side_effect=[[],[],[point]]) as query,patch.object(sc.time,'sleep'):
            result=sc.geocode('Rua Iacanga, 356, Americana, SP, Brasil')
        self.assertEqual(result[0]['tipo'],'rua_aproximada')
        self.assertIn('numero nao confirmado',result[0]['endereco'])
        self.assertEqual(query.call_count,3)
        self.assertEqual(query.call_args.args[1]['street'],'Rua Iacanga')

    def test_first_response_road_is_also_approximate(self):
        with patch.object(sc,'geocode_request',return_value=[{'tipo':'primary','endereco':'Rua Iacanga'}]):
            self.assertEqual(sc.geocode('Rua Iacanga, 356, Americana, SP')[0]['tipo'],'rua_aproximada')

    def test_lookup_does_not_put_complement_postcode_in_street(self):
        data=dict(nome_fantasia='VIDE BULA',descricao_tipo_de_logradouro='RUA',logradouro='IACANGA',numero='356',complemento='TERREO',bairro='JARDIM YPIRANGA',municipio='AMERICANA',uf='SP',cep='13468000')
        with TestClient(main.app) as client,patch.object(c,'last_cnpj',float('-inf')),patch.object(c,'fetch_cnpj',return_value=data):
            response=client.post('/api/concorrentes/cnpj/buscar',headers={'X-Price-Config':'1'},json={'cnpj':'46330650000104'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['endereco'],'RUA IACANGA, 356, AMERICANA, SP, Brasil')
