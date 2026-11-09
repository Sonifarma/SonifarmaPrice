import os,csv,io,math
from pathlib import Path
from datetime import datetime,timedelta
from decimal import Decimal
from fastapi import FastAPI,Query,HTTPException
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from fastapi.responses import HTMLResponse,StreamingResponse
from fastapi.staticfiles import StaticFiles

BASE=Path(__file__).resolve().parent.parent
app=FastAPI(title='Sonifarma Price Intelligence',version='1.7.9')
app.mount('/static',StaticFiles(directory=str(BASE/'static')),name='static')

def db():
 import psycopg2
 return psycopg2.connect(host=os.getenv('A7_HOST',''),port=int(os.getenv('A7_PORT','5432')),dbname=os.getenv('A7_DATABASE',''),user=os.getenv('A7_USER',''),password=os.getenv('A7_PASSWORD',''),connect_timeout=5,options='-c default_transaction_read_only=on -c statement_timeout=12000')

def demo_rows():
 def load(name):
  with (BASE/'amostras'/f'{name}.csv').open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f,delimiter=';'))
 prod={r['id']:r for r in load('produto')}; costs={r['produtoid']:r for r in load('custoproduto') if r['unidadenegocioid']==os.getenv('A7_UNIT','1')}; stocks={r['embalagemid']:r for r in load('estoque') if r['unidadenegocioid']==os.getenv('A7_UNIT','1')}
 result=[]
 for e in load('embalagem'):
  p=prod.get(e['produtoid']);
  if not p:continue
  c=costs.get(p['id'],{}); s=stocks.get(e['id'],{})
  result.append(dict(produto_id=p['id'],codigo=p['codigo'],descricao=p['descricao'],status=p['status'],tipo_preco=p.get('tipopreco'),embalagem_id=e['id'],ean=e['codigobarras'],apresentacao=e['descricao'],quantidade=e['quantidadeporembalagem'],preco=e['precovenda'],custo=c.get('custo'),customedio=c.get('customedio'),estoque=s.get('estoque'),vendas30=None,faturamento30=None))
 return result

SQL='''SELECT p.id AS produto_id,p.codigo,p.descricao,p.status,e.id AS embalagem_id,e.codigobarras AS ean,e.descricao AS apresentacao,e.quantidadeporembalagem AS quantidade,e.precovenda AS preco,c.custo,c.customedio,s.estoque,COALESCE(g.vendas30,0) AS vendas30,COALESCE(g.faturamento30,0) AS faturamento30 FROM produto p JOIN embalagem e ON e.produtoid=p.id LEFT JOIN LATERAL (SELECT cp.custo,cp.customedio FROM custoproduto cp WHERE cp.produtoid=p.id AND cp.unidadenegocioid=%s ORDER BY cp.id DESC LIMIT 1) c ON TRUE LEFT JOIN LATERAL (SELECT es.estoque FROM estoque es WHERE es.embalagemid=e.id AND es.unidadenegocioid=%s ORDER BY es.id DESC LIMIT 1) s ON TRUE LEFT JOIN (SELECT iv.embalagemid,SUM(iv.quantidade) AS vendas30,SUM(iv.valortotal) AS faturamento30 FROM itemvenda iv JOIN venda v ON v.id=iv.vendaid WHERE v.unidadenegocioid=%s AND iv.unidadenegocioid=%s AND v.status='F' AND iv.status='F' AND v.datahorafechamento >= CURRENT_DATE - INTERVAL '30 days' GROUP BY iv.embalagemid) g ON g.embalagemid=e.id WHERE (%s='' OR p.descricao ILIKE %s OR CAST(p.codigo AS TEXT) ILIKE %s OR e.codigobarras ILIKE %s) ORDER BY p.descricao,e.id LIMIT %s OFFSET %s'''

def mode():return os.getenv('MODE','demo').lower()
@app.get('/',response_class=HTMLResponse)
def home():return (BASE/'static'/'index.html').read_text(encoding='utf-8')
@app.get('/api/status')
def status():return {'mode':mode(),'unit':os.getenv('A7_UNIT','1'),'write_enabled':False,'pricing_enabled':False,'collector_enabled':False}
@app.get('/api/products')
def products(q:str='',limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)):
 if mode()=='demo':
  items=demo_rows(); q=q.casefold().strip();items=[x for x in items if q in str(x['descricao']).casefold() or q in str(x['ean']).casefold() or q in str(x['codigo']).casefold()];return {'items':items[offset:offset+limit],'total':len(items),'demo':True}
 if mode()!='postgres':raise HTTPException(400,'MODE inválido')
 try:
  with db() as conn:
   with conn.cursor() as cur:
    cur.execute(SQL,(int(os.getenv('A7_UNIT','1')),)*4+(q,'%'+q+'%','%'+q+'%','%'+q+'%',limit,offset))
    names=[d[0] for d in cur.description];data=[dict(zip(names,row)) for row in cur.fetchall()]
  for r in data:
   for k,v in r.items():
    if isinstance(v,Decimal):r[k]=float(v)
  return {'items':data,'total':None,'demo':False}
 except Exception as ex:raise HTTPException(503,'Falha na consulta ao Alpha7. Confira conexão, permissões, status e nomes das colunas. Detalhes técnicos no log do servidor.') from ex
@app.get('/api/diagnostic')
def diagnostic():
 if mode()=='demo':return {'mode':'demo','tables':['produto','embalagem','custoproduto','estoque','venda','itemvenda'],'message':'Modo demonstração: não há conexão com ERP.'}
 try:
  with db() as conn:
   with conn.cursor() as cur:
    cur.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=ANY(%s) ORDER BY table_name,ordinal_position",(['produto','embalagem','custoproduto','estoque','venda','itemvenda'],));rows=cur.fetchall()
  return {'mode':'postgres','columns':[{'table':t,'column':c} for t,c in rows]}
 except Exception as ex:raise HTTPException(503,'Não foi possível consultar o esquema do Alpha7.') from ex


# V1.1: pesquisa por raio em observações importadas, sem escrita no Alpha7.
import sqlite3, re, math
from fastapi import UploadFile, File
from datetime import timezone
LOCAL_DB=BASE/'data'/'mercado.sqlite3'
GROUPS={'supermercados','perfumarias','farmacias_redes','farmacias_independentes'}
def localdb():
 LOCAL_DB.parent.mkdir(exist_ok=True)
 conn=sqlite3.connect(str(LOCAL_DB),timeout=10)
 conn.execute('CREATE TABLE IF NOT EXISTS observacoes (id INTEGER PRIMARY KEY, ean TEXT NOT NULL, grupo TEXT NOT NULL, estabelecimento TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL, preco REAL NOT NULL, coletado_em TEXT NOT NULL, fonte TEXT NOT NULL, condicao TEXT NOT NULL, criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
 conn.execute('CREATE INDEX IF NOT EXISTS idx_obs_ean ON observacoes(ean)')
 return conn
def km(lat1,lon1,lat2,lon2):
 r=6371.0088;a1,a2=math.radians(lat1),math.radians(lat2);dl=math.radians(lat2-lat1);do=math.radians(lon2-lon1)
 return 2*r*math.asin(min(1,math.sqrt(math.sin(dl/2)**2+math.cos(a1)*math.cos(a2)*math.sin(do/2)**2)))
@app.get('/api/mercado/status')
def market_status():
 with localdb() as con: n=con.execute('SELECT COUNT(*) FROM observacoes').fetchone()[0]
 return {'observacoes':n,'coleta_automatica':False,'alteracao_erp':False,'origem':'observacoes locais por CSV; precos dos sites consultados separadamente','consulta_online':True,'fontes_online':['Drogal','Drogaria Sao Paulo'],'fontes_manuais':['Drogaria Todo Dia']}
@app.post('/api/mercado/importar')
async def market_import(arquivo:UploadFile=File(...)):
 # Somente arquivo local e estruturado, sem scraping nem conexão com sites externos.
 raw=await arquivo.read(2_000_001)
 if len(raw)>2_000_000:raise HTTPException(413,'Arquivo excede 2 MB')
 try:
  txt=raw.decode('utf-8-sig'); rows=list(csv.DictReader(io.StringIO(txt),delimiter=';'))
 except Exception:raise HTTPException(400,'CSV inválido. Use UTF-8 e separador ponto e vírgula.')
 if len(rows)>5000:raise HTTPException(400,'Máximo de 5000 registros por arquivo')
 expected={'ean','grupo','estabelecimento','latitude','longitude','preco','coletado_em','fonte','condicao'}
 if not rows or not expected.issubset(set(rows[0])):raise HTTPException(400,'Cabeçalhos obrigatórios: '+', '.join(sorted(expected)))
 valid=[]; errors=[]
 for i,r in enumerate(rows,2):
  try:
   ean=r['ean'].strip();grupo=r['grupo'].strip();nome=r['estabelecimento'].strip();fonte=r['fonte'].strip();cond=r['condicao'].strip()
   lat=float(r['latitude'].replace(',','.'));lon=float(r['longitude'].replace(',','.'));preco=float(r['preco'].replace(',','.'))
   data=datetime.fromisoformat(r['coletado_em'].strip()).date().isoformat()
   if not (re.fullmatch(r'\d{8,14}',ean) and grupo in GROUPS and 0<len(nome)<=150 and -90<=lat<=90 and -180<=lon<=180 and 0<preco<100000 and 0<len(fonte)<=500 and len(cond)<=200):raise ValueError()
   valid.append((ean,grupo,nome,lat,lon,preco,data,fonte,cond))
  except (ValueError,TypeError,KeyError,OverflowError):errors.append(i)
 if errors:raise HTTPException(400,{'mensagem':'Importação cancelada: linhas inválidas','linhas':errors[:30]})
 with localdb() as con:
  con.executemany('INSERT INTO observacoes(ean,grupo,estabelecimento,latitude,longitude,preco,coletado_em,fonte,condicao) VALUES(?,?,?,?,?,?,?,?,?)',valid)
 return {'importados':len(valid),'mensagem':'Importação concluída no banco local; Alpha7 não alterado.'}
@app.get('/api/mercado/comparar')
def market_compare(ean:str=Query(...,min_length=8,max_length=14),latitude:float|None=Query(None,ge=-90,le=90),longitude:float|None=Query(None,ge=-180,le=180),raio:float=Query(2,ge=0.5,le=50),dias:int=Query(7,ge=1,le=90),usar_centro:bool=False,centro_versao:int|None=Query(None,ge=1)):
 centro=None
 if usar_centro:
  if latitude is not None or longitude is not None:raise HTTPException(422,'Use o centro cadastrado ou coordenadas explicitas, nunca ambos.')
  from app.search_center import get_center
  centro=get_center(LOCAL_DB)
  if centro is None:raise HTTPException(422,'Cadastre e confirme o endereco do centro da pesquisa antes de consultar por raio.')
  if centro_versao is not None and centro_versao!=centro['versao']:raise HTTPException(409,'O centro da pesquisa foi alterado. Recarregue o cadastro e consulte novamente.')
  latitude,longitude=centro['latitude'],centro['longitude']
 if (latitude is None)!=(longitude is None):raise HTTPException(422,'Informe latitude e longitude juntas ou omita ambas.')
 geografico=latitude is not None
 limite=(datetime.now().date()-timedelta(days=dias)).isoformat()
 with localdb() as con:
  rows=con.execute('SELECT grupo,estabelecimento,latitude,longitude,preco,coletado_em,fonte,condicao FROM observacoes WHERE ean=? AND coletado_em>=?',(ean,limite)).fetchall()
 itens=[]
 for g,n,lat,lon,p,d,f,cond in rows:
  dist=km(latitude,longitude,lat,lon) if geografico else None
  if not geografico or dist<=raio:itens.append({'grupo':g,'estabelecimento':n,'distancia_km':round(dist,2) if dist is not None else None,'preco':p,'coletado_em':d,'fonte':f,'condicao':cond})
 itens.sort(key=lambda x:x['preco'])
 return {'ean':ean,'raio_km':raio if geografico else None,'filtro_geografico':geografico,'centro':centro,'observacoes':itens,'menor_preco':itens[0]['preco'] if itens else None,'aviso':'Dados importados, não verificados automaticamente. Preços condicionados não devem gerar ajustes automáticos.'}

# Consulta incremental, sem alterar os endpoints V1.1 existentes.
from app.product_review import make_router
app.include_router(make_router(lambda: db(), lambda: demo_rows(), SQL, lambda: mode()))

from app.market_products import make_router as make_market_products_router
app.include_router(make_market_products_router(lambda: db(), lambda: demo_rows(), lambda: mode()))

from app.search_center import make_router as make_search_center_router
app.include_router(make_search_center_router(lambda: LOCAL_DB))

from app.market_products import make_detail_router
app.include_router(make_detail_router(lambda: db(), lambda: demo_rows(), lambda: mode()))
from app.local_stores import make_router as make_local_stores_router
app.include_router(make_local_stores_router(lambda: LOCAL_DB, km))

from app.competitors import make_router as make_competitors_router
app.include_router(make_competitors_router(lambda: LOCAL_DB, km))

from app.online_prices import make_router as make_online_prices_router
app.include_router(make_online_prices_router(lambda: LOCAL_DB, km))
