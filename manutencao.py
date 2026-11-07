"""Atualizacao por pacote ZIP ou pasta, sem Git no servidor."""
import argparse
import ast
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parent
PACKAGE_URL = 'https://codeload.github.com/Sonifarma/SonifarmaPrice/zip/refs/heads/main'
ROOT_FILES = {
    'manutencao.py', 'requirements.txt', 'requirements-dev.txt', 'README.txt', 'README.md',
    'OPERACAO_LOCAL.md', 'CHANGELOG.md', 'AGENTS.md', '.gitignore', '.env.exemplo', '.env.example',
    'instalar.bat', 'iniciar.bat', 'ATUALIZAR_PRICE.bat', 'ATUALIZAR_V1_1.bat',
    'SONIFARMA_PRICE_CONTROLE.ps1', 'LEIA_PRIMEIRO_V1_1.txt',
}


def safe_path(root, name):
    path = root / name
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise RuntimeError('Link nao permitido: ' + str(path))
    return path


def code_files(root):
    names = {name for name in ROOT_FILES if (root / name).is_file()}
    for folder, extensions in [('app', {'.py'}), ('static', {'.html', '.js', '.css', '.csv', '.png', '.svg'}), ('docs', {'.md'})]:
        directory = root / folder
        if directory.is_symlink():
            raise RuntimeError('Pasta de codigo nao pode ser link: ' + folder)
        for path in directory.rglob('*') if directory.exists() else []:
            relative = path.relative_to(root)
            if path.is_file() and path.suffix.lower() in extensions and not any(p.startswith('.') or p == '__pycache__' for p in relative.parts):
                safe_path(root, relative)
                names.add(relative.as_posix())
    return names


def verify(archive):
    with zipfile.ZipFile(archive) as z, tempfile.TemporaryDirectory() as work:
        manifest = json.loads(z.read('manifesto.json'))
        if len(z.namelist()) != len(set(z.namelist())) or set(z.namelist()) != set(manifest) | {'manifesto.json'}:
            raise RuntimeError('Conteudo do backup difere do manifesto.')
        for name, expected in manifest.items():
            content = z.read(name)
            if hashlib.sha256(content).hexdigest() != expected:
                raise RuntimeError('Hash invalido: ' + name)
            if Path(name).suffix.lower() in {'.db', '.sqlite', '.sqlite3'}:
                restored = Path(work) / 'verificacao.sqlite3'
                restored.write_bytes(content)
                with closing(sqlite3.connect(restored)) as db:
                    if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                        raise RuntimeError('Banco invalido no backup: ' + name)
                restored.unlink()
    return len(manifest)


def backup(root, destination):
    root, destination = root.resolve(), destination.resolve()
    if destination == root or root in destination.parents:
        raise RuntimeError('Use destino de backup fora da pasta do projeto.')
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / ('SonifarmaPrice_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.zip')
    names = code_files(root)
    if (root / '.env').is_file():
        names.add('.env')
    for folder in ['data', 'amostras']:
        directory = root / folder
        if directory.is_symlink():
            raise RuntimeError('Pasta de dados nao pode ser link.')
        if directory.exists():
            names.update(p.relative_to(root).as_posix() for p in directory.rglob('*') if p.is_file() and not p.name.endswith(('-wal', '-shm', '-journal')))
    partial = archive.with_suffix('.tmp')
    manifest = {}
    try:
        with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as z, tempfile.TemporaryDirectory() as work:
            for name in sorted(names):
                path = safe_path(root, name)
                if path.suffix.lower() in {'.db', '.sqlite', '.sqlite3'}:
                    snapshot = Path(work) / 'snapshot.sqlite3'
                    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(snapshot)) as dst:
                        src.backup(dst)
                    content = snapshot.read_bytes()
                    snapshot.unlink()
                else:
                    content = path.read_bytes()
                manifest[name] = hashlib.sha256(content).hexdigest()
                z.writestr(name, content)
            z.writestr('manifesto.json', json.dumps(manifest, indent=2))
        verify(partial)
        partial.replace(archive)
    finally:
        partial.unlink(missing_ok=True)
    print('Backup verificado:', archive)
    return archive


def require_stopped():
    with socket.socket() as s:
        try:
            s.bind(('0.0.0.0', 8770))
        except OSError as exc:
            raise RuntimeError('Pare iniciar.bat com Ctrl+C. Porta 8770 ocupada.') from exc


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        pending = Path(f.name)
        f.write(content)
    try:
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def apply_package(root, source, destination):
    root, source = root.resolve(), source.resolve()
    if root == source:
        raise RuntimeError('Origem e instalacao devem ser diferentes.')
    require_stopped()
    required = {'app/main.py', 'static/index.html', 'requirements.txt', 'manutencao.py'}
    selected = code_files(source)
    if not required.issubset(selected):
        raise RuntimeError('Pacote incompleto: faltam ' + ', '.join(sorted(required - selected)))
    # Valida e congela todo o codigo antes de tocar na instalacao.
    contents = {}
    for name in sorted(selected):
        safe_path(root, name)
        content = safe_path(source, name).read_bytes()
        if name.endswith('.py'):
            ast.parse(content.decode('utf-8-sig'), filename=name)
        contents[name] = content
    archive = backup(root, destination)
    require_stopped()
    with zipfile.ZipFile(archive) as z:
        previous = {name: z.read(name) for name in selected if name in z.namelist()}
    changed = []
    try:
        for name, content in contents.items():
            changed.append(name)
            atomic_write(root / name, content)
    except Exception as exc:
        errors = []
        for name in reversed(changed):
            try:
                if name in previous:
                    atomic_write(root / name, previous[name])
                else:
                    (root / name).unlink(missing_ok=True)
            except OSError:
                errors.append(name)
        if errors:
            raise RuntimeError(f'Falha de copia e reversao incompleta: {errors}. Recupere pelo backup {archive}') from exc
        raise RuntimeError(f'Falha de copia; codigo anterior restaurado. Backup: {archive}') from exc
    print('Codigo atualizado por pacote. .env, data, .venv e outros sistemas preservados.')
    return archive


def download_package(target):
    request = Request(PACKAGE_URL, headers={'User-Agent': 'SonifarmaPrice-Updater'})
    with urlopen(request, timeout=60) as response, target.open('wb') as out:
        size = 0
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > 50_000_000:
                raise RuntimeError('Pacote excede 50 MB.')
            out.write(chunk)


def unpack(archive, destination):
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        if len(infos) > 5000 or sum(i.file_size for i in infos) > 100_000_000:
            raise RuntimeError('ZIP excede os limites de tamanho.')
        paths = set()
        for info in infos:
            name = info.filename
            path = PurePosixPath(name)
            if '\\' in name or ':' in name or path.is_absolute() or '..' in path.parts or name.casefold() in paths or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError('Caminho invalido no ZIP.')
            paths.add(name.casefold())
        z.extractall(destination)
    candidates = [p.parent.parent for p in destination.rglob('app/main.py')]
    if len(candidates) != 1:
        raise RuntimeError('ZIP deve conter uma unica raiz SonifarmaPrice.')
    return candidates[0]


def update(root, destination, source=None):
    require_stopped()
    with tempfile.TemporaryDirectory(prefix='sonifarma_price_') as work:
        work = Path(work)
        if source and source.is_dir():
            package = source
        else:
            archive = source or work / 'codigo.zip'
            if source is None:
                print('Baixando pacote oficial da branch main...')
                download_package(archive)
            package = unpack(archive, work / 'pacote')
        return apply_package(root, package, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('acao', choices=['update', 'backup', 'verify'])
    parser.add_argument('--destination', type=Path, default=ROOT.parent / 'BackupsSonifarmaPrice')
    parser.add_argument('--source', type=Path, help='Pasta extraida ou ZIP; omitido baixa main do GitHub')
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    if args.acao == 'verify':
        if not args.archive:
            parser.error('Informe --archive')
        print('Arquivos verificados:', verify(args.archive))
    else:
        require_stopped()
        if args.acao == 'backup':
            backup(ROOT, args.destination)
        else:
            update(ROOT, args.destination, args.source)
            print('Instalando dependencias no Python atual; se falhar, mantenha o painel parado.')
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True)
            print('Concluido. Execute iniciar.bat e valide http://localhost:8770.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, SyntaxError, subprocess.CalledProcessError, sqlite3.Error, zipfile.BadZipFile) as exc:
        raise SystemExit('ERRO: ' + str(exc))
