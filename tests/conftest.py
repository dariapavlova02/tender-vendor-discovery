"""Offline-only checks: no credentials, external requests or user database."""
import os
import socket

import pytest

os.environ['PYTHON_DOTENV_DISABLED'] = '1'
for key in list(os.environ):
    if key.endswith('_API_KEY') or key in {'GOOGLE_CLIENT_SECRET', 'AUTH_COOKIE_SECRET'}:
        os.environ.pop(key, None)
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'


def deny_network(*args, **kwargs):
    raise AssertionError('External network access is disabled in the offline test suite')


# Applied before collection as well as during tests.
socket.create_connection = deny_network
_original_connect = socket.socket.connect


def offline_connect(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        deny_network()
    return _original_connect(self, address)


socket.socket.connect = offline_connect


@pytest.fixture(autouse=True)
def isolated_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
