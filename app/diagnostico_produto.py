"""Diagnostico somente leitura do cadastro e compras de um EAN no servidor."""
import argparse
from contextlib import closing
from datetime import datetime
import json
import os
import re
from zoneinfo import ZoneInfo
from app import main as server, product_review as review


def exclusion_reasons(row, config, unit):
    reasons=[]
    if row.get('unidade')!=unit:reasons.append('Nota de outra unidade')
    if row.get('status')!=config['STATUS_VALUE']:reasons.append('Status da nota diferente do configurado')
    if row.get('movimento')!=config['MOVEMENT_VALUE']:reasons.append('Movimento nao adiciona estoque conforme configuracao')
    if row.get('tem_fornecedor') is not True:reasons.append('Nota sem fornecedor')
    if not row.get('entrada'):reasons.append('Nota sem data de entrada')
    if (review.number(row.get('quantidade')) or 0)<=0:reasons.append('Quantidade ausente ou nao positiva')
    if row.get('bonificacao') is not False:reasons.append('Bonificacao verdadeira ou nao informada')
    if row.get('sem_movimento') is not False:reasons.append('Item sem movimentacao ou indicador nao informado')
    if str(row.get('cfop') or '') not in config['CFOPS']:reasons.append('CFOP fora dos configurados para compra')
    return reasons


def rows(cursor):
    names=[d[0] for d in cursor.description]
    return [dict(zip(names,row)) for row in cursor.fetchall()]


def diagnose(ean, description=''):
    if not re.fullmatch(r'[0-9]{8,14}',ean):raise ValueError('Informe um EAN de 8 a 14 digitos.')
    if server.mode()!='postgres':raise ValueError('Execute no servidor com a configuracao postgres existente; o modo demo nao comprova dados reais.')
    unit=int(os.getenv('A7_UNIT','1'));config=review.purchase_config()
    today=datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    start,end=review.interval('45',today=today)
    result={'versao':server.app.version,'somente_leitura':True,'ean':ean,'unidade_configurada':unit,
            'periodo_45_dias':{'inicio':start,'fim':end},'cadastros':[],'compras_recentes':[],
            'limite_itens_notas':100}
    with closing(server.db()) as con:
        with con.cursor() as cur:
            cur.execute("SELECT p.id AS produto_id,p.codigo,p.descricao,p.status,p.tipopreco AS tipo_preco,e.id AS embalagem_id,e.codigobarras AS ean,e.descricao AS apresentacao FROM produto p JOIN embalagem e ON e.produtoid=p.id WHERE e.codigobarras=%s ORDER BY p.id,e.id LIMIT 50",(ean,))
            result['cadastros']=rows(cur)
            if not result['cadastros']:
                result['conclusao']='EAN nao encontrado no cadastro consultado pelo Price. Confira se o Alpha7 usa outro EAN para esta embalagem.'
                return result
            if description:
                for item in result['cadastros']:
                    joined=' '.join(str(item.get(k) or '') for k in ['descricao','apresentacao','codigo','ean'])
                    item['corresponde_texto_digitado']=description.strip().casefold() in joined.casefold()
            result['configuracao_compra']=config
            if config is None:
                result['conclusao']='Cadastro encontrado, mas a fonte de ultima compra nao esta configurada.'
                return result
            kind=review.check_purchase_columns(cur,config) if config.get('SOURCE')=='notafiscal' else review.check_entry_columns(cur,config)
            sql,params=review.build_query(server.SQL,config,kind,'ean',ean,None,None,0,False,False,50,0,'todos','todos','ultima_compra')
            cur.execute(sql,params)
            purchases=rows(cur)
            # Exporta somente identificadores, descricao e data; sem custos, clientes ou fornecedores.
            result['ultima_compra_reconhecida']=[{k:r.get(k) for k in ['produto_id','embalagem_id','ean','ultima_compra']} for r in purchases if r.get('ean')==ean]
            if config.get('SOURCE')=='notafiscal':
                schema='"'+config['SCHEMA']+'"'
                product_ids=list(dict.fromkeys(r['produto_id'] for r in result['cadastros']))
                cur.execute(f'''SELECT nf.id AS nota_id,nf.unidadenegocioid AS unidade,nf.status,
                  nf.tipomovimentacaofisica AS movimento,nf.fornecedorid IS NOT NULL AS tem_fornecedor,
                  nf.datahoraentrada AS entrada,nf.datahoraemissao AS emissao,item.embalagemid AS embalagem_id,
                  item.quantidade,item.bonificacao,item.itemsemmovimentacao AS sem_movimento,item.cfop::text AS cfop
                  FROM {schema}.notafiscal nf JOIN {schema}.itemnotafiscal item ON item.notafiscalid=nf.id
                  JOIN {schema}.embalagem e ON e.id=item.embalagemid WHERE e.produtoid=ANY(%s)
                  ORDER BY nf.datahoraentrada DESC NULLS LAST,nf.id DESC LIMIT 100''',(product_ids,))
                for row in rows(cur):
                    row['motivos_exclusao']=exclusion_reasons(row,config,unit)
                    row['aceita_pela_regra_compra']=not row['motivos_exclusao']
                    result['compras_recentes'].append(row)
            result['conclusao']='Confira a ultima compra reconhecida e os motivos de exclusao das notas. Uma compra aceita precisa estar no periodo; o texto digitado tambem precisa corresponder ao cadastro.'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ean');parser.add_argument('--descricao',default='')
    args=parser.parse_args()
    try:result=diagnose(args.ean,args.descricao)
    except Exception as exc:
        message=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
        raise SystemExit('Diagnostico nao concluido: '+message+'. Nenhuma alteracao foi feita.') from None
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
