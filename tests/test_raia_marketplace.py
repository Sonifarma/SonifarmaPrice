import unittest
from unittest.mock import patch
from app import raia,online_prices as online
from app.product_search import profile
from test_raia import data,document,URL


def partner():
 p=data();p['productData'].update(is3p=True,seller={'id':'unic','storeName':'Unic','active':True})
 return p

class MarketplaceTests(unittest.TestCase):
 def test_offer_has_distinct_seller_and_group_and_sale_price(self):
  p=partner();p['productData']['price_aux'].update(value_from=79.99,value_to=74.90)
  p['productData']['liveComposition']['livePrice']['valueTo']=74.90
  offer=raia.product_offer(p,URL,allow_marketplace=True)
  self.assertEqual(offer['preco'],74.90);self.assertEqual(offer['preco_regular'],79.99)
  self.assertTrue(offer['em_oferta']);self.assertEqual(offer['vendedor'],'Unic')
  self.assertTrue(offer['marketplace']);self.assertEqual(offer['abrangencia'],'marketplace')
  self.assertEqual(offer['grupo_online'],'Marketplace — vendedores externos')
  self.assertFalse(offer['filial_confirmada'])
  self.assertIsNone(raia.product_offer(p,URL,'0000000000000',allow_marketplace=True))
 def test_unknown_inactive_or_unavailable_sellers_are_rejected(self):
  for seller in [None,{}, {'id':'unic','storeName':'Unic','active':False},{'id':'unic','active':True}]:
   p=partner();p['productData']['seller']=seller
   self.assertIsNone(raia.product_offer(p,URL,allow_marketplace=True))
  p=partner();p['productData']['liveComposition']['liveStock']['qty']=0
  self.assertIsNone(raia.product_offer(p,URL,allow_marketplace=True))
  p=partner();p['productData']['name']='Kit C/3 Simeticona 40mg 20 comprimidos Medley'
  self.assertIsNone(raia.product_offer(p,URL,allow_marketplace=True))
 def test_same_ean_own_and_partner_are_kept_without_multiplying_search_duplicates(self):
  own=data();other=partner()
  for a in other['productData']['custom_attributes']:
   if a['attribute_code']=='url_key':a['value_string']=['produto-parceiro']
  search={'pageProps':{'results':{'products':[
   {'url':'/produto-teste.html','is1P':True,'isThirdPartner':False},
   {'url':'/produto-parceiro.html','is1P':False,'isThirdPartner':True},
   {'url':'/produto-parceiro.html','is1P':False,'isThirdPartner':True},
   {'url':'/kit.html','name':'Kit C/3 Produto','is1P':False,'isThirdPartner':True}]}}}
  calls=[]
  def fetch(source,path):
   calls.append(path)
   return document(search if path.startswith('/search?') else other if path=='/produto-parceiro.html' else own)
  offers=raia.offers(online.SOURCES['raia'],own['productData']['productEan'],fetch,ean=own['productData']['productEan'])
  self.assertEqual([o['vendedor'] for o in offers],['Droga Raia','Unic'])
  self.assertNotIn('/kit.html',calls)
 def test_browser_fallback_handles_unavailable_candidate_without_dereferencing_missing_offer(self):
  p=data();p['productData']['liveComposition']['liveStock']['qty']=0
  search={'pageProps':{'results':{'products':[{'url':'/produto-teste.html','is1P':True,'isThirdPartner':False}]}}}
  with patch.object(raia,'standard_browser') as browser:
   browser.return_value.__enter__.return_value.get.side_effect=[document(search),document(p)]
   rows=raia.offers(online.SOURCES['raia'],'simeticona',lambda *a:(_ for _ in ()).throw(ValueError()),wanted=profile('G SIMETICONA 40MG 20CP MEDL'))
  self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['oferta'])
