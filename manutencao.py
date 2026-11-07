"""Atualizacao local com Git, backup verificado e preservacao de dados."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import zipfile
from datetime import datetime

ROOT = Path(__file__).resolve().parent


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def protected(name):
    p = Path(name.lower())
    return (any(x in {'.git', '.venv', '__pycache__', 'data', 'backups'} for x in p.parts)
            or (p.name.startswith('.env') and p.name not in {'.env.exemplo', '.env.example'})
            or p.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.log', '.cred', '.key'})


def verify(archive):
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('manifesto.json'))
        if set(z.namelist()) != set(manifest) | {'manifesto.json'}:
            raise RuntimeError('Conteudo do backup difere do manifesto.')
        for name, expected in manifest.items():
            if hashlib.sha256(z.read(name)).hexdigest() != expected:
                raise RuntimeError('Hash invalido: ' + name)
    return len(manifest)


def backup(root, destination):
    destination = destination.resolve()
    if destination == root or root in destination.parents:
        raise RuntimeError('Use destino de backup fora da pasta do projeto.')
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / ('SonifarmaPrice_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.zip')
    names = set(git(root, 'ls-files').splitlines())
    if (root / '.env').is_file():
        names.add('.env')
    if (root / 'data').exists():
        names.update(p.relative_to(root).as_posix() for p in (root / 'data').rglob('*') if p.is_file())
    manifest = {}
    partial = archive.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as z:
            for name in sorted(names):
                path = root / name
                if path.is_symlink() or not path.is_file():
                    raise RuntimeError('Arquivo ausente ou link nao permitido: ' + name)
                # A aplicacao deve estar parada; valida os bancos antes de copiar.
                if path.suffix in {'.db', '.sqlite', '.sqlite3'}:
                    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
                        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                            raise RuntimeError('Banco invalido: ' + name)
                content = path.read_bytes()
                manifest[name] = hashlib.sha256(content).hexdigest()
                z.writestr(name, content)
            z.writestr('manifesto.json', json.dumps(manifest, indent=2))
        verify(partial)
        partial.rename(archive)
    finally:
        partial.unlink(missing_ok=True)
    print('Backup verificado:', archive)
    return archive


def require_stopped():
    with socket.socket() as s:
        try:
            s.bind(('0.0.0.0', 8770))
        except OSError as exc:
            raise RuntimeError('Pare o SonifarmaPrice (Ctrl+C no iniciar.bat). Porta 8770 ocupada.') from exc


def update(root, destination):
    require_stopped()
    if git(root, 'branch', '--show-current') != 'main':
        raise RuntimeError('Atualize somente na branch main.')
    if git(root, 'status', '--porcelain', '--untracked-files=normal'):
        raise RuntimeError('Existem arquivos alterados ou nao versionados. Preserve/revise antes de atualizar.')
    remote = git(root, 'remote', 'get-url', 'origin')
    if remote.rstrip('/').removesuffix('.git') != 'https://github.com/Sonifarma/SonifarmaPrice':
        raise RuntimeError('Origin deve apontar para https://github.com/Sonifarma/SonifarmaPrice.git')
    git(root, 'fetch', 'origin', 'main')
    target = git(root, 'rev-parse', 'FETCH_HEAD')
    subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', 'HEAD', target], check=True)
    incoming = git(root, 'ls-tree', '-r', '--name-only', target).splitlines()
    if any(protected(n) for n in incoming):
        raise RuntimeError('Atualizacao contem arquivos locais protegidos. Operacao cancelada.')
    if git(root, 'rev-parse', 'HEAD') == target:
        print('Codigo ja esta atualizado.')
        return
    previous = git(root, 'rev-parse', 'HEAD')
    backup(root, destination)
    require_stopped()
    git(root, 'merge', '--ff-only', target)
    print('Codigo atualizado. Commit anterior:', previous)
    print('Instalando dependencias; se falhar, mantenha o painel parado e repita a instalacao.')
    subprocess.run([str(root / '.venv' / 'Scripts' / 'python.exe'), '-m', 'pip', 'install', '-r', str(root / 'requirements.txt')], check=True)
    print('Concluido. Execute iniciar.bat e valide http://localhost:8770. Use Ctrl+F5 no navegador.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('acao', choices=['update', 'backup', 'verify'])
    p.add_argument('--destination', type=Path, default=ROOT.parent / 'BackupsSonifarmaPrice')
    p.add_argument('--archive', type=Path)
    args = p.parse_args()
    if args.acao == 'verify':
        if not args.archive:
            p.error('Informe --archive')
        print('Arquivos verificados:', verify(args.archive))
    else:
        require_stopped()
        if args.acao == 'backup':
            backup(ROOT, args.destination)
        else:
            update(ROOT, args.destination)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        raise SystemExit('ERRO: ' + str(exc))
