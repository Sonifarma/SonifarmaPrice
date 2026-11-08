"""Comparacao comercial por principio ativo e apresentacao, sem equivalencia terapeutica."""
import re
from app.product_search import profile,text,MAKERS

# Somente nomes explicitos: nunca traduz uma marca em principio ativo por semelhanca.
INGREDIENTS={'SIMETICONA','PARACETAMOL','IBUPROFENO','LORATADINA','DESLORATADINA','OMEPRAZOL',
 'PANTOPRAZOL','AMOXICILINA','AZITROMICINA','NIMESULIDA','CETOPROFENO','CETOCONAZOL',
 'FLUCONAZOL','ACICLOVIR','ALBENDAZOL','IVERMECTINA','ANLODIPINO','ATENOLOL','ENALAPRIL',
 'CAPTOPRIL','HIDROCLOROTIAZIDA','FUROSEMIDA','ESPIRONOLACTONA','SINVASTATINA','ROSUVASTATINA',
 'ATORVASTATINA','METFORMINA','GLICLAZIDA','GLIMEPIRIDA','PREDNISONA','PREDNISOLONA'}
SPEC_KEYS={'PRINCIPIO ATIVO','PRINCIPIOS ATIVOS','SUBSTANCIA ATIVA','COMPOSICAO'}


def explicit_ingredient(title):
 value=text(title)
 found=sorted(name for name in INGREDIENTS if re.search(r'\b'+name+r'\b',value))
 # Associacoes requerem campo estruturado, para nao omitir um segundo componente.
 if len(found)!=1 or '+' in title or re.search(r'\b(ASSOCIAD|ASSOCIAC|COMPOST)',value):return None
 without_maker=value
 for maker in sorted(MAKERS,key=len,reverse=True):
  without_maker=re.sub(r'\b'+re.escape(maker)+r'\b',' ',without_maker)
 core=profile(without_maker)['principais']
 # Palavras adicionais podem indicar outro componente nao reconhecido.
 core=[w for w in core if w not in {'GOTAS','SOLUCAO','SUSPENSAO','CREME','POMADA','GEL','ORAL','ML','MG','MASTIGAVEL','EFERVESCENTE','SUBLINGUAL','LIBERACAO','PROLONGADA','RETARD','GASTRORRESISTENTE'}]
 if core!=[found[0]]:return None
 return found[0]


def ingredient(product,title):
 for key,value in product.items():
  if text(key) not in SPEC_KEYS:continue
  if isinstance(value,str):value=[value]
  if isinstance(value,list) and value and all(isinstance(v,str) for v in value):
   raw=' + '.join(sorted(value))
   if len(value)!=1 or re.search(r'[+;/]',raw):return ''
   return text(raw)
  return ''
 return explicit_ingredient(title)


def signature(title,active=None):
 parsed=profile(title);expanded=text(title)
 if active is None:active=explicit_ingredient(title)
 if not active or '+' in title or len(parsed['doses'])!=1:return None
 form=parsed['forma']
 if not form:
  form=next((f for f in ['GOTAS','SUSPENSAO','SOLUCAO','CREME','POMADA','GEL'] if re.search(r'\b'+f+r'\b',expanded)),None)
 volumes=sorted(re.findall(r'\b(\d+(?:[.,]\d+)?)\s*ML\b',expanded))
 # Sem forma e conteudo completos, nao agrega precos de embalagens diferentes.
 if not form or not (parsed['quantidade'] or volumes):return None
 modifiers=[word for word in ['MASTIGAVEL','EFERVESCENTE','SUBLINGUAL','PROLONGADA','RETARD','GASTRORRESISTENTE','NASAL','OFTALMICA','INJETAVEL','MOLE','MOLES'] if word in expanded.split()]
 return {'principio_ativo':active,'doses':parsed['doses'],'forma':form,'quantidade':parsed['quantidade'],
         'volumes_ml':volumes,'modificadores':modifiers}


def reference(description,sources,ean):
 # Primeiro procura metadados do EAN exato. Um candidato escolhido nao redefine a referencia.
 refs=[o.get('composicao') for s in sources for o in s['ofertas'] if o.get('ean')==ean and o.get('composicao')]
 if refs:
  return refs[0] if all(r==refs[0] for r in refs) else None
 return signature(description)


def query_text(ref):
 return (ref['principio_ativo']+' '+' '.join(ref['doses'])+' '+ref['forma']).lower()
