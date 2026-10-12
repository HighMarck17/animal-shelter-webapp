"""
Tests for apps/core/storage.py (Cloudinary media storage). The Cloudinary SDK
and HTTP calls are mocked: no network, no credentials.
"""
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import SimpleTestCase, TestCase, override_settings

from apps.core.storage import CloudinaryMediaStorage
from conftest import DogFactory

CLOUDINARY_SETTINGS = {
    'CLOUDINARY_STORAGE': {'CLOUD_NAME': 'shelter-demo', 'API_KEY': 'key', 'API_SECRET': 'secret'},
    'MEDIA_URL': '/media/',
}
BASE_URL = 'https://res.cloudinary.com/shelter-demo/image/upload/v1/'
PUBLIC_ID = 'media/dogs/main/2026/10/fido_ab12cd'


@override_settings(**CLOUDINARY_SETTINGS)
class CloudinaryMediaStorageTest(SimpleTestCase):

    def setUp(self):
        self.storage = CloudinaryMediaStorage()

    def test_url_of_stored_public_id(self):
        self.assertEqual(self.storage.url(PUBLIC_ID), BASE_URL + PUBLIC_ID)

    def test_url_adds_media_prefix(self):
        self.assertEqual(self.storage.url('dogs/main/2026/10/fido_ab12cd'), BASE_URL + PUBLIC_ID)

    @patch('cloudinary.uploader.upload', return_value={'public_id': PUBLIC_ID})
    def test_save_uploads_to_prefixed_folder_and_returns_public_id(self, upload):
        name = self.storage.save('dogs/main/2026/10/fido.jpg', ContentFile(b'img'))
        self.assertEqual(name, PUBLIC_ID)
        (uploaded,), options = upload.call_args
        self.assertEqual(uploaded.name, 'fido.jpg')
        self.assertEqual(options, {
            'use_filename': True,
            'resource_type': 'image',
            'tags': 'media',
            'folder': 'media/dogs/main/2026/10',
        })

    @patch('cloudinary.uploader.destroy', return_value={'result': 'ok'})
    def test_delete_invalidates_cdn_cache(self, destroy):
        self.assertTrue(self.storage.delete(PUBLIC_ID))
        destroy.assert_called_once_with(PUBLIC_ID, invalidate=True, resource_type='image')

    @patch('cloudinary.uploader.destroy', return_value={'result': 'not found'})
    def test_delete_missing_file(self, _destroy):
        self.assertFalse(self.storage.delete(PUBLIC_ID))

    def _http(self, status, headers=None, data=b''):
        return patch('apps.core.storage._http.request',
                     return_value=MagicMock(status=status, headers=headers or {}, data=data))

    def test_exists(self):
        with self._http(200) as request:
            self.assertTrue(self.storage.exists(PUBLIC_ID))
        request.assert_called_once_with('HEAD', BASE_URL + PUBLIC_ID)
        with self._http(404):
            self.assertFalse(self.storage.exists(PUBLIC_ID))
        with self._http(500), self.assertRaises(OSError):
            self.storage.exists(PUBLIC_ID)

    def test_size(self):
        with self._http(200, headers={'Content-Length': '2048'}):
            self.assertEqual(self.storage.size(PUBLIC_ID), 2048)

    def test_open(self):
        with self._http(200, data=b'img'):
            self.assertEqual(self.storage.open(PUBLIC_ID).read(), b'img')
        with self._http(404), self.assertRaises(FileNotFoundError):
            self.storage.open(PUBLIC_ID)

    def test_available_name_is_not_checked_remotely(self):
        with patch('apps.core.storage._http.request') as request:
            self.assertEqual(self.storage.get_available_name('dogs/a.jpg', max_length=6), 'dogs/a')
        request.assert_not_called()


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'apps.core.storage.CloudinaryMediaStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    **CLOUDINARY_SETTINGS,
)
class CloudinaryDogImageTest(TestCase):

    @patch('cloudinary.uploader.upload', return_value={'public_id': PUBLIC_ID})
    def test_dog_image_round_trip(self, _upload):
        """Upload through the model, then edit the dog keeping the photo:
        the stored public ID has no extension and must not fail validation."""
        dog = DogFactory()
        dog.main_image.save('fido.jpg', ContentFile(b'img'))
        dog.refresh_from_db()
        self.assertEqual(dog.main_image.name, PUBLIC_ID)
        self.assertEqual(dog.main_image.url, BASE_URL + PUBLIC_ID)
        with patch('apps.core.storage._http.request') as request:
            dog.full_clean()
        request.assert_not_called()
