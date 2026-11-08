import os,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from app import raia,todo_dia

class BrowserModeTests(unittest.TestCase):
 def test_raia_windows_defaults_visible_and_can_explicitly_use_headless(self):
  with patch.dict(os.environ,{'PRICE_RAIA_BROWSER_MODE':'auto'}):
   self.assertTrue(raia.browser_mode('nt'));self.assertFalse(raia.browser_mode('posix'))
  with patch.dict(os.environ,{'PRICE_RAIA_BROWSER_MODE':'headless'}):self.assertFalse(raia.browser_mode('nt'))
  with patch.dict(os.environ,{'PRICE_RAIA_BROWSER_MODE':'visible'}):self.assertTrue(raia.browser_mode('posix'))
  with patch.dict(os.environ,{'PRICE_RAIA_BROWSER_MODE':'invalido'}):
   with self.assertRaises(raia.RaiaReadError):raia.browser_mode('nt')
 def test_standard_browser_enables_javascript_and_keeps_navigation_on_source(self):
  driver=Mock();browser=driver.chromium.launch.return_value;context=browser.new_context.return_value;page=context.new_page.return_value
  page.goto.return_value.status=200;page.goto.return_value.body.return_value=b'User-agent: *\nAllow: /\n';page.url='https://www.drogaraia.com.br/robots.txt'
  with patch('playwright.sync_api.sync_playwright') as playwright:
   playwright.return_value.start.return_value=driver
   with todo_dia.Browser(host='www.drogaraia.com.br',validator=raia.browser_url,render=True,visible=True) as reader:
    self.assertEqual(reader.trace[0]['etapa'],'ROBOTS')
   self.assertFalse(driver.chromium.launch.call_args.kwargs['headless'])
   self.assertTrue(browser.new_context.call_args.kwargs['java_script_enabled'])
   callback=context.route.call_args.args[1]
   resource=Mock();resource.request=SimpleNamespace(resource_type='script',url='https://www.drogaraia.com.br/script.js')
   callback(resource);resource.continue_.assert_called_once()
   navigation=Mock();navigation.request=SimpleNamespace(resource_type='document',url='https://evil.test/pagina',frame=SimpleNamespace(parent_frame=None))
   callback(navigation);navigation.abort.assert_called_once()
   browser.close.assert_called_once();driver.stop.assert_called_once()
 def test_todo_dia_keeps_its_existing_lightweight_browser_default(self):
  reader=todo_dia.Browser();self.assertFalse(reader.render);self.assertFalse(reader.visible)
 def test_http_errors_identify_robots_or_product_page(self):
  reader=todo_dia.Browser(host='www.drogaraia.com.br',validator=raia.browser_url)
  reader.robots=None;reader.last=0;reader.page=Mock();reader.page.goto.return_value.status=403
  with self.assertRaises(todo_dia.PublicDocumentError) as failure:reader.get('https://www.drogaraia.com.br/robots.txt')
  self.assertEqual(failure.exception.code,'HTTP_403_ROBOTS')

 def test_detects_chrome_in_windows_32bit_installation_directory(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);chrome=root/'x86/Google/Chrome/Application/chrome.exe';chrome.parent.mkdir(parents=True);chrome.touch()
   with patch.dict(os.environ,{'PRICE_BROWSER_EXECUTABLE':'','ProgramFiles':str(root/'programs'),'ProgramFiles(x86)':str(root/'x86'),'LOCALAPPDATA':str(root/'local')}):
    self.assertEqual(raia.system_browser('nt'),str(chrome))
