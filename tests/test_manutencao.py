import importlib.util
from pathlib import Path
import sqlite3
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
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        self.source = self.base / 'source'
        for folder, code in [(self.root, 'print(1)'), (self.source, 'print(2)')]:
            (folder / 'app').mkdir(parents=True)
            (folder / 'static').mkdir()
            (folder / 'app' / 'main.py').write_text(code)
            (folder / 'static' / 'index.html').write_text('teste')
            (folder / 'manutencao.py').write_text('pass')
            (folder / 'requirements.txt').write_text('')
        (self.root / '.env').write_text('MODE=postgres')
        self.destination = self.base / 'backups'
        patcher = patch.object(m, 'require_stopped')
        patcher.start()
        self.addCleanup(patcher.stop)

    def package(self):
        archive = self.base / 'release.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for path in self.source.rglob('*'):
                if path.is_file():
                    z.write(path, 'SonifarmaPrice-main/' + path.relative_to(self.source).as_posix())
        return archive

    def test_folder_update_without_git_preserves_local_files(self):
        (self.root / 'data').mkdir()
        (self.root / 'data' / 'local.txt').write_text('preservado')
        (self.root / '.venv').mkdir()
        (self.root / '.venv' / 'python.exe').write_text('ambiente proprio')
        (self.source / '.env').write_text('NAO COPIAR')
        (self.source / 'data').mkdir()
        (self.source / 'data' / 'local.txt').write_text('NAO COPIAR')
        with patch.object(m.subprocess, 'run', side_effect=AssertionError('Nao executar Git ou outros processos')):
            archive = m.update(self.root, self.destination, self.source)
        self.assertEqual((self.root / 'app' / 'main.py').read_text(), 'print(2)')
        self.assertEqual((self.root / '.env').read_text(), 'MODE=postgres')
        self.assertEqual((self.root / 'data' / 'local.txt').read_text(), 'preservado')
        self.assertEqual((self.root / '.venv' / 'python.exe').read_text(), 'ambiente proprio')
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(z.read('app/main.py'), b'print(1)')
        self.assertGreater(m.verify(archive), 0)

    def test_zip_update_and_default_download(self):
        archive = self.package()
        with patch.object(m, 'download_package', side_effect=lambda dest: dest.write_bytes(archive.read_bytes())) as download:
            m.update(self.root, self.destination)
        download.assert_called_once()
        self.assertEqual((self.root / 'app' / 'main.py').read_text(), 'print(2)')

    def test_incomplete_package_stops_before_backup(self):
        (self.source / 'manutencao.py').unlink()
        with self.assertRaisesRegex(RuntimeError, 'incompleto'):
            m.update(self.root, self.destination, self.source)
        self.assertFalse(self.destination.exists())
        self.assertEqual((self.root / 'app' / 'main.py').read_text(), 'print(1)')

    def test_syntax_error_stops_before_backup(self):
        (self.source / 'app' / 'main.py').write_text('def broken(')
        with self.assertRaises(SyntaxError):
            m.update(self.root, self.destination, self.source)
        self.assertFalse(self.destination.exists())

    def test_copy_failure_rolls_back_code(self):
        real = m.atomic_write
        failed = False
        def write(path, content):
            nonlocal failed
            if path.name == 'manutencao.py' and not failed:
                failed = True
                raise OSError('falha simulada')
            return real(path, content)
        with patch.object(m, 'atomic_write', side_effect=write):
            with self.assertRaisesRegex(RuntimeError, 'anterior restaurado'):
                m.update(self.root, self.destination, self.source)
        self.assertEqual((self.root / 'app' / 'main.py').read_text(), 'print(1)')
        self.assertEqual((self.root / '.env').read_text(), 'MODE=postgres')

    def test_backup_failure_prevents_copy(self):
        with patch.object(m, 'backup', side_effect=OSError('sem espaco')):
            with self.assertRaises(OSError):
                m.update(self.root, self.destination, self.source)
        self.assertEqual((self.root / 'app' / 'main.py').read_text(), 'print(1)')

    def test_zip_traversal_rejected(self):
        archive = self.base / 'bad.zip'
        for name in ['../outside.py', '/outside.py', 'C:/outside.py', 'dir\\outside.py']:
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr(name, 'pass')
            with self.assertRaisesRegex(RuntimeError, 'Caminho invalido'):
                m.unpack(archive, self.base / 'unpacked')
        self.assertFalse((self.base / 'outside.py').exists())

    def test_backup_sqlite_includes_committed_wal(self):
        (self.root / 'data').mkdir()
        path = self.root / 'data' / 'mercado.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE exemplo (valor TEXT)')
            db.execute("INSERT INTO exemplo VALUES ('preservado')")
            db.commit()
            archive = m.backup(self.root, self.destination)
        m.verify(archive)
        with zipfile.ZipFile(archive) as z:
            restored = self.base / 'restored.sqlite3'
            restored.write_bytes(z.read('data/mercado.sqlite3'))
            self.assertFalse(any(n.endswith('-wal') for n in z.namelist()))
        with sqlite3.connect(restored) as db:
            self.assertEqual(db.execute('SELECT valor FROM exemplo').fetchone(), ('preservado',))

    def test_corruption_rejected(self):
        archive = m.backup(self.root, self.destination)
        with zipfile.ZipFile(archive) as z:
            contents = {n: z.read(n) for n in z.namelist()}
        contents['app/main.py'] = b'changed'
        with zipfile.ZipFile(archive, 'w') as z:
            for name, content in contents.items():
                z.writestr(name, content)
        with self.assertRaisesRegex(RuntimeError, 'Hash invalido'):
            m.verify(archive)

    def test_backup_destination_inside_project_rejected(self):
        with self.assertRaises(RuntimeError):
            m.backup(self.root, self.root / 'backups')


if __name__ == '__main__':
    unittest.main()
