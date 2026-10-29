"""Test Suite for StreamFetch Universal Downloader"""

import sys
import os
import pytest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.engine.extractor import media_extractor
from app.engine.downloader import media_downloader
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_extractor_empty_url_raises_error():
    with pytest.raises(ValueError):
        media_extractor.inspect_url("")


def test_downloader_empty_url_raises_error():
    with pytest.raises(ValueError):
        media_downloader.download("")


def test_web_ui_dashboard_served():
    res = client.get("/")
    assert res.status_code == 200
    assert "StreamFetch" in res.text
    assert "<form" in res.text


def test_health_check_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "download_dir" in data


def test_info_endpoint_validation():
    # Empty URL rejected
    res = client.post("/api/v1/info", json={"url": ""})
    assert res.status_code == 400


def test_file_server_not_found():
    res = client.get("/api/v1/files/nonexistent_test_file_99999.mp4")
    assert res.status_code == 404


def test_file_server_path_traversal_protection():
    res = client.get("/api/v1/files/../../secret.txt")
    assert res.status_code in [403, 404]
