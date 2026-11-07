"""Mostra somente estrutura de tabelas candidatas; nao consulta dados de pessoas."""
from contextlib import closing
import json
from app.main import db, mode


def main():
    if mode() != 'postgres':
        raise SystemExit('Configure MODE=postgres no .env existente antes do diagnostico.')
    patterns = ['%notafiscal%', '%recebiment%', '%entrada%', '%moviment%estoque%', '%historicocusto%']
    with closing(db()) as con:
        with con.cursor() as cursor:
            cursor.execute('SELECT table_schema,table_name,column_name,data_type FROM information_schema.columns WHERE table_schema NOT IN (%s,%s) AND table_name ILIKE ANY(%s) ORDER BY table_schema,table_name,ordinal_position LIMIT 600', ('pg_catalog', 'information_schema', patterns))
            rows = cursor.fetchall()
    print(json.dumps({'somente_leitura': True, 'limite_colunas': 600,
                      'colunas': [dict(zip(['schema', 'tabela', 'coluna', 'tipo'], row)) for row in rows]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
