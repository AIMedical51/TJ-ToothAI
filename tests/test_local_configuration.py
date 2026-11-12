"""Offline regression checks for local configuration and report/QR routing.

Run with both services' dependencies installed:
    python -m unittest discover -s tests -v
No real image, credential, inference, or agent service is used.
"""

import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlparse

from PIL import Image
import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sample_image():
    buffer = io.BytesIO()
    Image.new('RGB', (48, 32), 'white').save(buffer, format='JPEG')
    buffer.seek(0)
    return buffer


class LocalConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = tempfile.TemporaryDirectory(prefix='tjtooth-test-')
        cls.environment = patch.dict(os.environ, {
            'TJT_DATA_DIR': cls.data.name,
            'ROBOFLOW_API_KEY': '',
            'TONGJI_AGENT_API_KEY': '',
            'TONGJI_AGENT_BASE_URL': 'https://agent.example.com/api/proxy',
            'TONGJI_AGENT_USER_ID': 'demo-user',
            'PUBLIC_BASE_URL': 'https://tooth.example.com',
            'QRCODE_API_URL': '/v1/create-qr-code/',
            'QRCODE_BG_PATH': str(ROOT / 'qrcode-server/qrcode_background.png'),
            'MPLCONFIGDIR': str(Path(cls.data.name) / 'matplotlib'),
        })
        cls.environment.start()
        sys.path.insert(0, str(ROOT / 'www/tjtooth'))
        cls.web = load_module('tjtooth_test_app', ROOT / 'www/tjtooth/app.py')
        cls.qr = load_module('tjtooth_test_qr', ROOT / 'qrcode-server/app.py')
        cls.web.app.config['TESTING'] = True
        cls.qr.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()
        cls.data.cleanup()
        sys.path.remove(str(ROOT / 'www/tjtooth'))

    def setUp(self):
        self.client = self.web.app.test_client()
        self.qr_client = self.qr.app.test_client()
        self.network = patch(
            'requests.sessions.Session.request',
            side_effect=AssertionError('Unexpected external HTTP request'),
        )
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_pages_start_without_credentials(self):
        for path in ['/', '/about', '/caries', '/services', '/feature', '/science_videos']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
        with self.assertRaisesRegex(RuntimeError, 'ROBOFLOW_API_KEY'):
            self.web.require_inference_client()
        result = self.web.generate_report_with_agent('[]', {'name': 'demo'})
        self.assertIn('TONGJI_AGENT_API_KEY', result['progress'][0])

    def test_dotenv_uses_repo_root_and_preserves_process_environment(self):
        with tempfile.TemporaryDirectory(prefix='tjtooth-config-test-') as temp:
            repo = Path(temp)
            module_dir = repo / 'www/tjtooth'
            module_dir.mkdir(parents=True)
            (module_dir / 'runtime_config.py').write_text(
                (ROOT / 'www/tjtooth/runtime_config.py').read_text()
            )
            (repo / '.env').write_text(
                'TJT_DATA_DIR=local-data\nROBOFLOW_API_KEY=file-demo-value\nTJT_PORT=5123\n'
            )
            environment = os.environ.copy()
            for key in ['TJT_DATA_DIR', 'TJT_PORT']:
                environment.pop(key, None)
            environment['ROBOFLOW_API_KEY'] = 'process-demo-value'
            code = (
                'import sys; sys.path.insert(0, sys.argv[1]); import runtime_config as c; '
                'assert c.ROBOFLOW_API_KEY == "process-demo-value"; '
                'assert c.PORT == 5123; assert c.DATA_DIR == c.REPO_ROOT / "local-data"; '
                'assert c.REPORT_DIR.is_dir()'
            )
            subprocess.run([sys.executable, '-c', code, str(module_dir)],
                           env=environment, cwd='/tmp', check=True, capture_output=True)

    def test_missing_upload_and_missing_key_are_explicit(self):
        self.assertEqual(self.client.post('/predict').status_code, 400)
        self.assertEqual(self.client.post('/predict_multiple').status_code, 400)
        response = self.client.post('/predict', data={
            'file': (sample_image(), 'demo.jpg'),
            'patient_data': json.dumps({'name': 'demo', 'age': 30, 'gender': 'female'}),
        })
        self.assertEqual(response.status_code, 500)
        self.assertIn('ROBOFLOW_API_KEY', response.get_json()['error'])
        response = self.client.post('/detect/caries', json={'image_url': 'https://example.com/demo.jpg'})
        self.assertEqual(response.status_code, 500)
        self.assertIn('ROBOFLOW_API_KEY', response.get_json()['error'])

    def test_uploads_use_configured_runtime_directory(self):
        def no_detections(image, path):
            self.assertTrue(Path(path).resolve().is_relative_to(Path(self.data.name).resolve()))
            return image, None

        with patch.object(self.web, 'infer_and_annotate_for_all', side_effect=no_detections):
            response = self.client.post('/predict_multiple', data={
                'files': [(sample_image(), 'one.jpg'), (sample_image(), 'two.jpg')],
                'patient_data': json.dumps({'name': 'demo', 'age': 30, 'gender': 'female'}),
            })
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result['image_count'], 2)
        self.assertEqual(len(result['annotated_images']), 2)
        self.assertNotIn('report_url', result)
        info_path = Path(self.data.name) / 'patient_info' / result['info_filename']
        self.assertEqual(json.loads(info_path.read_text())['image_count'], 2)

    def test_report_routes_and_configured_qr_url(self):
        report_id = 'offline-demo'
        payload = {
            'patient_data': {'name': 'demo', 'age': 30, 'gender': 'female'},
            'detection_results': '[]',
            'agent_response': 'Offline test report',
            'annotated_image': base64.b64encode(sample_image().getvalue()).decode(),
            'timestamp': '2026-11-12T12:00:00',
        }
        report_path = Path(self.data.name) / 'reports' / f'agent_report_{report_id}.json'
        report_path.write_text(json.dumps(payload))
        self.assertEqual(self.client.get(f'/api/detection_report/{report_id}').get_json(), payload)
        page = self.client.get(f'/detection_report/{report_id}')
        self.assertEqual(page.status_code, 200)
        self.assertIn('new URL("/v1/create-qr-code/"', page.get_data(as_text=True))
        redirect = self.client.get(f'/download_pdf/{report_id}')
        self.assertEqual(redirect.status_code, 302)
        self.assertEqual(redirect.headers['Location'], f'/printable_report/{report_id}')
        self.assertEqual(self.client.get(redirect.headers['Location']).status_code, 200)

    def test_detected_upload_saves_readable_report_without_agent_key(self):
        detections = self.web.sv.Detections(
            xyxy=np.array([[2, 2, 20, 20]], dtype=float),
            confidence=np.array([0.9]),
            class_id=np.array([0]),
            data={'class_name': np.array(['caries'])},
        )
        with patch.object(self.web, 'infer_and_annotate_for_all',
                          return_value=(np.zeros((32, 48, 3), dtype=np.uint8), detections)):
            response = self.client.post('/predict', data={
                'file': (sample_image(), 'demo.jpg'),
                'patient_data': json.dumps({'name': 'demo', 'age': 30, 'gender': 'female'}),
            })
        self.assertEqual(response.status_code, 200)
        report_url = response.get_json()['report_url']
        self.assertTrue(report_url.startswith('https://tooth.example.com/detection_report/'))
        report_id = urlparse(report_url).path.rsplit('/', 1)[-1]
        saved = self.client.get('/api/detection_report/' + report_id).get_json()
        self.assertIsNone(saved['agent_response'])
        self.assertIn('TONGJI_AGENT_API_KEY', saved['debug_info']['progress'][0])
        self.assertEqual(json.loads(saved['detection_results'])[0]['class_name'], 'caries')

    def test_image_save_and_read_use_same_directory(self):
        with self.web.app.test_request_context('/'):
            url = self.web.save_and_get_output_url('caries', 'demo.jpg', np.zeros((32, 48, 3), dtype=np.uint8))
            annotated = self.web.save_annotated_image_and_get_url(np.zeros((32, 48, 3), dtype=np.uint8), 'offline')
        self.assertTrue(url.startswith('https://tooth.example.com/images/caries/'))
        with self.client.get(urlparse(url).path) as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(annotated['status'], 'success')
        self.assertTrue(Path(annotated['file_path']).resolve().is_relative_to(Path(self.data.name).resolve()))
        with self.client.get(urlparse(annotated['url']).path) as response:
            self.assertEqual(response.status_code, 200)

    def test_old_html_report_has_working_public_url(self):
        payload = {'name': 'demo', 'age': 30, 'gender': 'female'}
        for field in ['caries_num', 'caries_level', 'filling_num', 'filling_level',
                      'dentalstain_level', 'calculus_level', 'hypodontia_num',
                      'hypodontia_level', 'periodontitis_level']:
            payload['toothData_' + field] = 0
        response = self.client.post('/generate_report', json=payload)
        self.assertEqual(response.status_code, 200)
        url = response.get_json()['file_url']
        self.assertTrue(url.startswith('https://tooth.example.com/view_report/'))
        with self.client.get(urlparse(url).path) as page:
            self.assertEqual(page.status_code, 200)
            self.assertIn('demo', page.get_data(as_text=True))

    def test_failed_upload_does_not_attach_old_placeholder(self):
        first = Mock(status_code=200)
        first.json.return_value = {'Conversation': {'AppConversationID': 'demo-conversation'}}
        second = Mock(status_code=200, text='{"answer":"offline response"}')
        fixture = Path(self.data.name) / 'annotated_images/demo.jpg'
        fixture.write_bytes(sample_image().getvalue())
        with patch.object(self.web, 'TONGJI_AGENT_API_KEY', 'test-only-value'), \
             patch.object(self.web.requests, 'post', side_effect=[first, second]) as post, \
             patch.object(self.web, 'upload_file_to_obs', return_value={'success': False, 'error': 'offline'}):
            result = self.web.generate_report_with_agent('[]', {'name': 'demo'}, str(fixture))
        self.assertEqual(result['agent_response'], 'offline response')
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].args[0], 'https://agent.example.com/api/proxy/api/v1/create_conversation')
        self.assertEqual(post.call_args_list[0].kwargs['headers']['APIKey'], 'test-only-value')
        body = json.loads(post.call_args_list[1].kwargs['data'])
        self.assertEqual(body['QueryExtends']['Files'], [])
        self.assertEqual(body['UserID'], 'demo-user')

    def test_qr_background_fallback_and_private_cache(self):
        self.assertEqual(self.qr_client.get('/health').get_json(), {'status': 'ok'})
        self.assertEqual(self.qr_client.get('/v1/create-qr-code/').status_code, 400)
        response = self.qr_client.get('/v1/create-qr-code/', query_string={
            'data': 'https://example.com/report/demo', 'name': 'demo', 'size': '290x290',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'image/png')
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        with Image.open(io.BytesIO(response.data)) as output:
            self.assertEqual(output.size, (1280, 720))
        with patch.object(self.qr, 'BG_PATH', '/nonexistent/test-background.png'):
            response = self.qr_client.get('/v1/create-qr-code/', query_string={'data': 'demo', 'size': '160x240'})
        with Image.open(io.BytesIO(response.data)) as output:
            self.assertEqual(output.size, (160, 160))


if __name__ == '__main__':
    unittest.main()
