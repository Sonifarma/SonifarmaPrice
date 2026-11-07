import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('manutencao', Path(__file__).resolve().parents[1] / 'manutencao.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        self.root.mkdir()
        subprocess.run(['git', 'init', '-b', 'main', str(self.root)], check=True, capture_output=True)
        (self.root / 'app.py').write_text('print(1)')
        (self.root / '.gitignore').write_text('.env\ndata/\n')
        subprocess.run(['git', '-C', str(self.root), 'add', 'app.py', '.gitignore'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test', '-c', 'user.email=test@local', 'commit', '-m', 'initial'], check=True, capture_output=True)
        self.destination = self.root.parent / 'backups'

    def test_backup_preserves_config_and_database(self):
        (self.root / '.env').write_text('MODE=demo')
        (self.root / 'data').mkdir()
        db_path = self.root / 'data' / 'mercado.sqlite3'
        with sqlite3.connect(db_path) as db:
            db.execute('create table example (value text)')
            db.execute("insert into example values ('preservado')")
        archive = m.backup(self.root, self.destination)
        self.assertEqual(m.verify(archive), 4)
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(z.read('.env'), b'MODE=demo')
            restored = self.root.parent / 'restored.sqlite3'
            restored.write_bytes(z.read('data/mercado.sqlite3'))
        with sqlite3.connect(restored) as db:
            self.assertEqual(db.execute('select value from example').fetchone(), ('preservado',))
        self.assertEqual((self.root / '.env').read_text(), 'MODE=demo')

    def test_corruption_is_rejected(self):
        archive = m.backup(self.root, self.destination)
        with zipfile.ZipFile(archive) as z:
            contents = {n: z.read(n) for n in z.namelist()}
        contents['app.py'] = b'changed'
        with zipfile.ZipFile(archive, 'w') as z:
            for n, data in contents.items():
                z.writestr(n, data)
        with self.assertRaisesRegex(RuntimeError, 'Hash invalido'):
            m.verify(archive)

    def test_destination_inside_project_rejected(self):
        with self.assertRaises(RuntimeError):
            m.backup(self.root, self.root / 'backups')

    def test_dirty_worktree_blocks_update_before_fetch(self):
        (self.root / 'app.py').write_text('changed')
        with patch.object(m, 'require_stopped'):
            with self.assertRaisesRegex(RuntimeError, 'alterados'):
                m.update(self.root, self.destination)
        self.assertFalse(self.destination.exists())

    def test_fast_forward_preserves_local_data(self):
        remote = self.root.parent / 'remote.git'
        source = self.root.parent / 'source'
        for args in [
            ['clone', '--bare', str(self.root), str(remote)],
            ['-C', str(self.root), 'remote', 'add', 'origin', str(remote)],
            ['clone', str(remote), str(source)],
        ]:
            subprocess.run(['git', *args], check=True, capture_output=True)
        (source / 'app.py').write_text('print(2)')
        for args in [
            ['-C', str(source), 'add', 'app.py'],
            ['-C', str(source), '-c', 'user.name=Test', '-c', 'user.email=test@local', 'commit', '-m', 'update'],
            ['-C', str(source), 'push', 'origin', 'main'],
        ]:
            subprocess.run(['git', *args], check=True, capture_output=True)
        (self.root / '.env').write_text('MODE=demo')
        (self.root / 'data').mkdir()
        (self.root / 'data' / 'local.txt').write_text('preservado')
        real_git = m.git
        real_run = subprocess.run
        pip_calls = []

        def git_command(root, *args):
            if args == ('remote', 'get-url', 'origin'):
                return 'https://github.com/Sonifarma/SonifarmaPrice.git'
            return real_git(root, *args)

        def run_command(args, **kwargs):
            if 'pip' in args:
                pip_calls.append(args)
                return subprocess.CompletedProcess(args, 0)
            return real_run(args, **kwargs)

        with patch.object(m, 'require_stopped'), patch.object(m, 'git', side_effect=git_command), patch.object(m.subprocess, 'run', side_effect=run_command):
            m.update(self.root, self.destination)
        self.assertEqual((self.root / 'app.py').read_text(), 'print(2)')
        self.assertEqual((self.root / '.env').read_text(), 'MODE=demo')
        self.assertEqual((self.root / 'data' / 'local.txt').read_text(), 'preservado')
        self.assertEqual(len(pip_calls), 1)
        archive, = self.destination.glob('*.zip')
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(z.read('app.py'), b'print(1)')

    def test_reserved_paths(self):
        for name in ['.env', 'data/mercado.sqlite3', '.venv/python.exe', 'password.cred']:
            self.assertTrue(m.protected(name))
        self.assertFalse(m.protected('.env.exemplo'))
        self.assertFalse(m.protected('app/main.py'))


if __name__ == '__main__':
    unittest.main()
