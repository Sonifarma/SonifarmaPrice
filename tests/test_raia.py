import copy,json,unittest
from unittest.mock import patch
from app import raia,online_prices as online,todo_dia
from test_online_prices import catalog_fixture,EAN
from test_todo_dia import product as todo_product,html as todo_html,URL as TODO_URL

URL='https://www.drogaraia.com.br/produto-teste.html'

def data():
 return {'productData':dict(productEan=EAN,name='Simeticona 40mg 20 comprimidos Medley',is3p=False,seller=None,status=1,
  custom_attributes=[{'attribute_code':'ean','value_string':[EAN]},{'attribute_code':'url_key','value_string':['produto-teste']}],
  price_aux={'value_from':20,'value_to':12,'lmpm_qty':None,'lmpm_value_to':None},
  liveComposition={'livePrice':{'valueTo':10,'pixPrice':None,'bestPrice':None},'liveStock':{'qty':1}},pbm=None,pbmOfferTypes=None)}

def document(props):return '<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'props':{'pageProps':props}})+'</script>'

class RaiaTests(unittest.TestCase):
 def test_public_sale_over_regular_price_and_pix_offer_with_condition(self):
  offer=raia.product_offer(data(),URL,EAN)
  self.assertEqual(offer['preco'],10);self.assertEqual(offer['preco_regular'],20);self.assertTrue(offer['em_oferta'])
  modified=data();modified['productData']['liveComposition']['livePrice']['pixPrice']=9
  self.assertEqual(raia.product_offer(modified,URL,EAN)['preco'],9)
  self.assertIn('Pix',raia.product_offer(modified,URL,EAN)['condicao'])
 def test_personal_best_price_and_quantity_discount_are_not_unconditional_unit_price(self):
  modified=data();p=modified['productData'];p['liveComposition']['livePrice']['bestPrice']=1;p['pbm']={'price':2};p['price_aux'].update(lmpm_qty=3,lmpm_value_to=5)
  offer=raia.product_offer(modified,URL,EAN);self.assertEqual(offer['preco'],10)
  self.assertIn('PBM',offer['condicao']);self.assertIn('quantidade',offer['condicao'])
 def test_wrong_ean_marketplace_unavailable_and_invalid_prices_are_rejected(self):
  self.assertIsNone(raia.product_offer(data(),URL,'0000000000000'))
  for key,value in [('is3p',True),('seller',{'name':'Parceiro'}),('status',0)]:
   modified=data();modified['productData'][key]=value;self.assertIsNone(raia.product_offer(modified,URL))
  modified=data();modified['productData']['liveComposition']['liveStock']['qty']=0
  self.assertIsNone(raia.product_offer(modified,URL))
  for value in [0,True,float('nan'),float('inf'),.001]:
   modified=data();modified['productData']['liveComposition']['livePrice']['valueTo']=value;modified['productData']['price_aux']['value_to']=value
   self.assertIsNone(raia.product_offer(modified,URL),value)
  with self.assertRaises(ValueError):raia.product_offer(data(),'https://www.drogaraia.com.br/outro.html')
 def test_search_product_url_is_canonical_and_sponsored_partners_are_excluded(self):
  search={'pageProps':{'results':{'products':[{'url':'/produto-teste.html?origin=search','is1P':True,'isThirdPartner':False},{'url':'/parceiro.html','is1P':False,'isThirdPartner':True},{'url':'https://evil.test/roubo','is1P':True,'isThirdPartner':False}]}}}
  calls=[]
  def fetch(source,path):calls.append(path);return document(search if path.startswith('/search?') else data())
  offers=raia.offers(online.SOURCES['raia'],EAN,fetch,ean=EAN)
  self.assertEqual(len(offers),1);self.assertEqual(calls,['/search?w='+EAN,'/produto-teste.html'])
 def test_shared_cnpj_of_drogasil_does_not_imply_raia_store_in_radius(self):
  source=online.SOURCES['raia']
  self.assertTrue(online.matches({'nome':'Droga Raia','cnpj':None},source))
  self.assertTrue(online.matches({'nome':'Droga Raia Americana','cnpj':None},source))
  self.assertFalse(online.matches({'nome':'Drogasil','cnpj':'60746948000112'},source))
 def test_existing_sources_use_sale_price_and_expose_regular_price(self):
  products=catalog_fixture();offer=products[0]['items'][0]['sellers'][0]['commertialOffer'];offer.update(Price=12.34,ListPrice=20)
  parsed=online.parse_offers(products,online.SOURCES['drogal'],EAN)[0]
  self.assertEqual(parsed['preco'],12.34);self.assertEqual(parsed['preco_regular'],20);self.assertTrue(parsed['em_oferta'])
  product=todo_product();product['Items'][0].update(RetailPrice=12,ListPrice=20,PromotionPrice=9)
  parsed=todo_dia.parse_product(todo_html(product),TODO_URL)[0]
  self.assertEqual(parsed['preco'],9);self.assertEqual(parsed['preco_regular'],20);self.assertTrue(parsed['em_oferta'])
