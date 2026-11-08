"""Diagnostico local do raio e teste publico Raia; nao consulta nem altera o ERP."""
import argparse,json,re
from app import main,online_prices as online,search_center,todo_dia,raia


def report(ean,radius,description='SORO FISIOLOGICO C/10 AMP 5ML'):
 path=main.LOCAL_DB;center=search_center.get_center(path)
 stores=online.within_radius(path,center,radius,main.km) if center else []
 related=[store for store in stores if online.matches(store,online.SOURCES['raia'])]
 result={'versao':main.app.version,'ean':ean,'raio_diagnostico_km':radius,'centro_cadastrado':bool(center),
  'concorrentes_no_raio':len(stores),'raias_reconhecidas_no_raio':[{'nome':s['nome'],'distancia_km':s['distancia_km'],'grupo':s['grupo']} for s in related],
  'catalogo_raia':'pendente','ofertas_teste':[],
  'modo_navegador_raia':'visivel' if raia.browser_mode() else 'headless','javascript_raia':True,'navegador_sistema_configurado':bool(raia.system_browser())}
 try:
  offers=online.catalog(online.SOURCES['raia'],ean)
  result.update(catalogo_raia='consultado',ofertas_teste=[{'produto':o['produto'],'ean':o['ean'],'preco':o['preco'],'url':o['url'],'metodo':o.get('metodo','http_publico')} for o in offers])
 except Exception as exc:
  result.update(catalogo_raia='falha',tipo_erro=online.failure_code(exc))
 if not related:result['orientacao']='Raia nao identificada no cadastro deste raio: confira centro, distancia, nome e site da loja. O teste de catalogo e independente do cadastro e nao adiciona precos ao grafico.'
 elif result['catalogo_raia']=='falha':result['orientacao']='A loja foi reconhecida, mas o acesso ao catalogo falhou. Confira internet e a instalacao Chromium do Playwright no servidor.'
 elif not result['ofertas_teste']:result['orientacao']='A busca publica nao retornou oferta valida para este EAN. Confira a apresentacao e os candidatos por descricao.'
 else:result['orientacao']='Raia reconhecida e preco obtido. Recarregue a tela com Ctrl+F5, confira o mesmo raio e use Atualizar precos online; confira tambem o grupo da loja.'
 todo_stores=[store for store in stores if online.matches(store,online.SOURCES['tododia'])]
 todo={'lojas_reconhecidas_no_raio':[{'nome':s['nome'],'distancia_km':s['distancia_km']} for s in todo_stores]}
 try:
  offers=todo_dia.lookup(path,online.profile(description),ean=ean,force=True)
  todo.update(catalogo='consultado',ofertas_teste=[{'produto':o['produto'],'ean':o['ean'],'preco':o['preco'],'url':o['url']} for o in offers])
 except Exception as exc:todo.update(catalogo='falha',tipo_erro=online.failure_code(exc))
 result['todo_dia']=todo

 return result


def main_cli():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ean',default='7896230304536');parser.add_argument('--raio',type=float,default=2);parser.add_argument('--descricao',default='SORO FISIOLOGICO C/10 AMP 5ML');args=parser.parse_args()
 if not re.fullmatch(r'[0-9]{8,14}',args.ean) or not .5<=args.raio<=50:parser.error('Informe EAN e raio de 0.5 a 50 km validos.')
 print(json.dumps(report(args.ean,args.raio,args.descricao),ensure_ascii=False,indent=2))


if __name__=='__main__':main_cli()
