"""Exporta somente nomes/tipos de colunas para mapear a ultima compra no Alpha7."""
from contextlib import closing
from datetime import datetime
import json
from app.main import BASE,db


def main():
    patterns=['%compra%','%entrada%','%recebiment%','%notafiscal%','%itemnota%','%custoproduto%']
    try:
        with closing(db()) as con:
            with con.cursor() as cursor:
                cursor.execute("SELECT table_schema,table_name,column_name,data_type FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') AND (table_name IN ('produto','embalagem') OR table_name ILIKE ANY(%s)) ORDER BY table_schema,table_name,ordinal_position LIMIT 1200",(patterns,))
                columns=[dict(zip(['schema','tabela','coluna','tipo'],row)) for row in cursor.fetchall()]
        result={'somente_leitura':True,'objetivo':'Mapear ultima compra ao fornecedor, com unidade, identificador do produto/embalagem e status finalizado. Datas de custo nao comprovam compra.','limite':1200,'colunas':columns}
        folder=BASE/'data';folder.mkdir(exist_ok=True)
        target=folder/('diagnostico_compras_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json')
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Diagnostico salvo em:',target)
        print('Somente estrutura de tabelas e colunas; nenhum dado de cliente, fornecedor ou senha foi exportado.')
    except Exception as exc:
        raise SystemExit('Nao foi possivel obter a estrutura do Alpha7 ('+type(exc).__name__+'). Confira a conexao existente no servidor.') from None


if __name__=='__main__':main()
