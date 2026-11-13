"""Expansao de abreviacoes e conferencia de candidatos por apresentacao."""
import re
import unicodedata

ALIASES={'SAB':'SABONETE','INF':'INFANTIL','GLIC':'GLICERINA','GLICER':'GLICERINA','AMP':'AMPOLAS','AMPS':'AMPOLAS','AMPOLA':'AMPOLAS','FLACONETE':'FLACONETES','GTS':'GOTAS','FRD':'FRALDA','GERIA':'GERIATRICA','GERIAT':'GERIATRICA','CLAS':'CLASSICA',
 'CPS':'CAPSULAS','UNIAOQ':'UNIAO QUIMICA','UNIAOQUIMICA':'UNIAO QUIMICA','CAP':'CAPSULAS','CAPS':'CAPSULAS','CAPSULA':'CAPSULAS','CP':'COMPRIMIDOS','CPR':'COMPRIMIDOS','CPRS':'COMPRIMIDOS','COMP':'COMPRIMIDOS','COMPRIMIDO':'COMPRIMIDOS',
 'UN':'UNIDADES','UND':'UNIDADES','UNID':'UNIDADES','UNIDS':'UNIDADES','MEDL':'MEDLEY','MOME':'MOMENTA'}
MAKERS={'UNIAO QUIMICA','MEDLEY','MOMENTA','EUROFARMA','EMS','CIMED','GERMED','TEUTO','ACHE','PRATI','NEO QUIMICA','GLOBO','BIOSSINTETICA','BIOSINTETICA'}

def text(value):
 value=unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().upper()
 value=re.sub(r'(\d)([A-Z])',r'\1 \2',value)
 value=re.sub(r'[^A-Z0-9.,/ ]',' ',value)
 return ' '.join(ALIASES.get(word,word) for word in value.split())


def profile(value):
 expanded=text(value)
 # C/10 indica quantidade; C/5 ML indica conteudo, nao cinco unidades.
 expanded=re.sub(r'\bC\s*/?\s*(\d+)\b(?!\s*(?:ML|MG|MCG|G)\b)',r'\1 UNIDADES',expanded)
 generic=bool(re.match(r'^G\s+',expanded))
 if generic:expanded=re.sub(r'^G\s+','',expanded)
 dose=re.findall(r'\b(\d+(?:[.,]\d+)?)\s*(MCG|MG|G)(?:\s*/\s*(ML))?\b',expanded)
 doses=sorted({number.replace(',','.')+unit+('/'+ratio if ratio else '') for number,unit,ratio in dose})
 amount=re.search(r'\b(\d+)\s*(CAPSULAS|COMPRIMIDOS|UNIDADES|SACHES|AMPOLAS|FLACONETES)\b',expanded)
 if not amount:amount=re.search(r'\bC\s*/?\s*(\d+)\b',expanded)
 quantity=int(amount.group(1)) if amount else None
 form=next((word for word in ['CAPSULAS','COMPRIMIDOS','SACHES','AMPOLAS','FLACONETES'] if word in expanded.split()),None)
 diaper='FRALDA' in expanded.split()
 size_match=re.search(r'\b(XXG|XG|GG|G|M|P)\b',expanded) if diaper else None
 maker=next((m for m in sorted(MAKERS,key=len,reverse=True) if re.search(r'\b'+m+r'\b',expanded)),None)
 if re.search(r'\b20\s+BI\b',expanded):core=['20','BI']
 elif 'COTIDIAN' in expanded:core=['COTIDIAN','FRALDA']
 else:
  rest=expanded
  # Bebe ja identifica a linha infantil; muitos catalogos omitem esse adjetivo.
  if 'SABONETE' in expanded.split() and 'BEBE' in expanded.split():rest=re.sub(r'\bINFANTIL\b',' ',rest)
  if maker:rest=re.sub(r'\b'+re.escape(maker)+r'\b',' ',rest)
  rest=re.sub(r'\b\d+(?:[.,]\d+)?\s*(?:MCG|MG|ML|G)(?:\s*/\s*ML)?\b',' ',rest)
  rest=re.sub(r'\b\d+\s*(?:CAPSULAS|COMPRIMIDOS|UNIDADES|SACHES|AMPOLAS|FLACONETES)\b',' ',rest)
  stop={'GEN','GENERICO','COM','DE','DA','DO','C','CLASSICA','GERIATRICA','MOLE','MOLES','CAPSULAS','COMPRIMIDOS','UNIDADES','SACHES','AMPOLAS','FLACONETES','GOTAS'}|MAKERS
  core=[w for w in rest.split() if len(w)>=3 and w not in stop and not w.isdigit()][:4]
 query='cotidian' if core==['COTIDIAN','FRALDA'] else ' '.join(core)
 if doses:query+=' '+doses[0].lower()
 if maker and core!=['20','BI']:query+=' '+maker.lower()
 return {'original':value,'descricao':expanded+(' GENERICO' if generic else ''),'consulta':query.strip().lower(),
  'principais':core,'doses':doses,'quantidade':quantity,'forma':form,'tamanho':size_match.group(1) if size_match else None,
  'volumes_ml':sorted({v.replace(',','.') for v in re.findall(r'\b(\d+(?:[.,]\d+)?)\s*ML\b',expanded)}),'fabricante':maker,'linha_classica':diaper and 'CLASSICA' in expanded,'generico':generic}


def compare(wanted,title,brand=''):
 actual=profile(title);joined=text(title+' '+brand);pending=[];checks=[]
 if 'SABONETE' in wanted['principais'] and any(re.fullmatch(r'\d+(?:[.,]\d+)?G',dose) for dose in wanted['doses']) and actual['volumes_ml'] and not actual['doses']:return None
 if not wanted['principais'] or any(not re.search(r'\b'+re.escape(w)+r'\b',joined) for w in wanted['principais']):return None
 for key,label in [('doses','Dosagem'),('quantidade','Quantidade'),('forma','Apresentacao'),('tamanho','Tamanho'),('volumes_ml','Volume')]:
  required=wanted.get(key);found=actual.get(key)
  if not required:continue
  if found and found!=required:return None
  if not found:pending.append(label+' nao informada no titulo')
  else:checks.append(label+' confere')
 if wanted['linha_classica'] and 'CLASSICA' not in joined:
  if any(w in joined for w in ['PLUS','NOTURNA','DERMACARE']):return None
  pending.append('Conferir linha Classica/Bem Estar na embalagem')
 if wanted['fabricante']:
  if re.search(r'\b'+wanted['fabricante']+r'\b',joined):checks.append('Fabricante confere')
  elif wanted['fabricante']=='MOMENTA' and re.search(r'\b20\s+BI\b',joined) and text(brand) in {'','20 BI','EUROFARMA','MOMENTA'}:pending.append('Conferir fabricante/versao Momenta ou Eurofarma na embalagem')
  elif actual['fabricante'] or profile(brand)['fabricante'] or (text(brand) and text(brand) not in {' '.join(wanted['principais']),wanted['fabricante']}):return None
  else:pending.append('Fabricante nao informado; conferir na embalagem')
 if wanted['generico'] and 'GENERICO' not in joined:pending.append('Categoria generica nao informada no titulo')
 return {'conferencias':checks,'pendencias':pending,'pontuacao':len(checks)*10-len(pending)}


def normalized_maker(brand):
 return next((m for m in MAKERS if text(brand)==m),None)
