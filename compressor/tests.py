import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .compressor_engine import HEIC_EXTENSIONS, WebCompressor


class HeicUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='secret123')
        self.client.force_login(self.user)

    @override_settings(TEMP_ROOT=tempfile.gettempdir())
    def test_upload_accepts_heic_extension(self):
        upload = SimpleUploadedFile(
            'sample.heic',
            b'not-a-real-heic-but-extension-validation-should-pass',
            content_type='image/heic',
        )

        response = self.client.post(
            reverse('compressor:upload'),
            {
                'files': upload,
                'settings': '{}',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('session_id', response.json())


class CompressorOutputTests(TestCase):
    def test_heic_files_keep_jpeg_output_even_when_larger(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir)
            input_path = session_path / 'photo.heic'
            input_path.parent.mkdir(parents=True, exist_ok=True)
            input_path.write_bytes(b'heic-bytes')

            compressor = WebCompressor(session_path)
            output_path = compressor.compressed_path / 'photo_compressed.jpg'
            output_path.write_bytes(b'larger-jpeg-output')

            with patch.object(WebCompressor, 'analyze_image', return_value={
                'file_size_mb': 0.000001,
                'is_png_transparent': False,
            }):
                with patch.object(WebCompressor, 'determine_compression_category', return_value={
                    'quality': 90,
                    'max_dimension': None,
                    'category': 'D - Small',
                    'aggressive': False,
                }):
                    with patch('compressor.compressor_engine.Image.open') as mock_open:
                        image = mock_open.return_value.__enter__.return_value
                        image.mode = 'RGB'
                        image.size = (100, 100)
                        image.save.side_effect = lambda *args, **kwargs: None

                        success, _, _, _ = compressor.compress_image(input_path)

            self.assertTrue(success)
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.suffix.lower(), '.jpg')
            self.assertIn(input_path.suffix.lower(), HEIC_EXTENSIONS)


class AppConfigTests(TestCase):
    def test_ready_registers_heif_opener(self):
        import compressor as compressor_module

        from .apps import CompressorConfig

        config = CompressorConfig('compressor', compressor_module)

        with patch('pillow_heif.register_heif_opener') as register_mock:
            config.ready()

        register_mock.assert_called_once_with()
