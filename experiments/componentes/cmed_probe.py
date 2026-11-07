"""Inspecao de estrutura XLSX CMED; nao determina teto aplicavel ao produto."""
import argparse
from itertools import islice
import json
from pathlib import Path
import unicodedata
from openpyxl import load_workbook


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '')) if not unicodedata.combining(c)).strip().upper()


def inspect_workbook(path):
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        notes = []
        schema_errors = []
        for sheet in book:
            rows = sheet.iter_rows(values_only=True)
            for index, row in enumerate(islice(rows, 100), 1):
                if any(normalize(value) == 'SUBSTANCIA' for value in row):
                    columns = [str(v or '').strip() for v in row]
                    if not any(normalize(c).startswith('EAN') for c in columns):
                        schema_errors.append('Planilha sem coluna EAN.')
                        break
                    if not any(normalize(c).startswith('PMC') for c in columns):
                        schema_errors.append('Planilha sem coluna PMC; nao confundir PMVG com PMC.')
                        break
                    samples = list(islice(rows, 5))
                    return {'aba': sheet.title, 'linha_cabecalho': index, 'colunas': columns,
                            'linhas_declaradas': sheet.max_row, 'notas': notes,
                            'linhas_amostradas': len(samples),
                            'aviso': 'Leitura estrutural; vigencia, aliquota, identidade e teto aplicavel ainda precisam de validacao.'}
                notes.extend(str(v)[:300] for v in row if v is not None)
        if schema_errors:
            raise ValueError(' '.join(schema_errors))
        raise ValueError('Cabecalho SUBSTANCIA nao encontrado nas primeiras 100 linhas de cada aba.')
    finally:
        book.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arquivo', type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect_workbook(args.arquivo), ensure_ascii=False, indent=2))
