"""
Media storage on Cloudinary, built on the official cloudinary SDK.

Replaces the unmaintained django-cloudinary-storage (last release 2020) and
keeps its naming scheme, so the files it stored resolve to the same public IDs
and URLs:
- names get the MEDIA_URL prefix ('media/'), and their directory becomes the
  Cloudinary folder;
- uploads keep the original file name plus Cloudinary's unique suffix;
- the returned public ID (no extension for images) is what the database stores.
"""
import os

import certifi
import cloudinary
import cloudinary.uploader
import urllib3
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.core.files.uploadedfile import UploadedFile
from django.utils.deconstruct import deconstructible

_http = urllib3.PoolManager(
    cert_reqs='CERT_REQUIRED',
    ca_certs=certifi.where(),
    timeout=urllib3.Timeout(connect=5, read=30),
    retries=urllib3.Retry(total=2, backoff_factor=0.5),
)


@deconstructible
class CloudinaryMediaStorage(Storage):
    resource_type = 'image'
    tag = 'media'

    def __init__(self):
        credentials = settings.CLOUDINARY_STORAGE
        cloudinary.config(
            cloud_name=credentials['CLOUD_NAME'],
            api_key=credentials['API_KEY'],
            api_secret=credentials['API_SECRET'],
            secure=True,
        )
        prefix = settings.MEDIA_URL.lstrip('/')
        self.prefix = prefix if not prefix or prefix.endswith('/') else prefix + '/'

    def _with_prefix(self, name):
        return name if name.startswith(self.prefix) else self.prefix + name

    def _save(self, name, content):
        name = self._with_prefix(name.replace('\\', '/'))
        options = {'use_filename': True, 'resource_type': self.resource_type, 'tags': self.tag}
        folder = os.path.dirname(name)
        if folder:
            options['folder'] = folder
        # UploadedFile gives the SDK the file name that use_filename relies on
        response = cloudinary.uploader.upload(UploadedFile(content, name), **options)
        return response['public_id']

    def delete(self, name):
        response = cloudinary.uploader.destroy(name, invalidate=True, resource_type=self.resource_type)
        return response['result'] == 'ok'

    def url(self, name):
        resource = cloudinary.CloudinaryResource(
            self._with_prefix(name), default_resource_type=self.resource_type
        )
        return resource.url

    def exists(self, name):
        response = _http.request('HEAD', self.url(name))
        if response.status == 404:
            return False
        self._raise_for_status(response)
        return True

    def size(self, name):
        response = _http.request('HEAD', self.url(name))
        self._raise_for_status(response)
        return int(response.headers['Content-Length'])

    def _open(self, name, mode='rb'):
        response = _http.request('GET', self.url(name))
        if response.status == 404:
            raise FileNotFoundError(name)
        self._raise_for_status(response)
        file = ContentFile(response.data, name=name)
        file.mode = mode
        return file

    def get_available_name(self, name, max_length=None):
        # Cloudinary appends a unique suffix itself; no existence check needed
        return name if max_length is None else name[:max_length]

    @staticmethod
    def _raise_for_status(response):
        if response.status >= 400:
            raise OSError(f'Cloudinary responded {response.status}')
