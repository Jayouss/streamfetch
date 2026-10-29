"""Test Suite for StreamFetch Universal Downloader"""

import sys
import os
from unittest.mock import patch, MagicMock
import pytest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.engine.extractor import media_extractor
from app.engine.downloader import media_downloader
from app.core.config import settings
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


def test_cookie_status_endpoint():
    res = client.get("/api/v1/cookies/status")
    assert res.status_code == 200
    assert "active" in res.json()
    assert "message" in res.json()


def test_cookie_upload_and_delete(tmp_path):
    orig_cookie_file = settings.COOKIE_FILE
    temp_cookie_path = str(tmp_path / "temp_test_cookies.txt")
    settings.COOKIE_FILE = temp_cookie_path

    try:
        fake_cookie_content = b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1799999999\tSID\tsample_session_val\n"
        res = client.post("/api/v1/cookies/upload", files={"file": ("cookies.txt", fake_cookie_content, "text/plain")})
        assert res.status_code == 200
        assert res.json()["status"] == "SAVED"

        # Verify status is now active
        status_res = client.get("/api/v1/cookies/status")
        assert status_res.json()["active"] is True

        # Delete cookies
        del_res = client.delete("/api/v1/cookies/delete")
        assert del_res.status_code == 200
    finally:
        settings.COOKIE_FILE = orig_cookie_file


def test_custom_stream_expired_url_raises_clear_error():
    # Expired video on jwplyr gives specific error
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 301
        mock_resp.headers = {"Location": "/404"}
        mock_get.return_value = mock_resp

        with pytest.raises(ValueError) as excinfo:
            media_extractor.inspect_url("https://jwplyr.com/e/4g80d06x099k")
        assert "jwplyr.com" in str(excinfo.value)
        assert "404" in str(excinfo.value)


def test_custom_stream_success_resolution():
    with patch("app.engine.custom_resolvers.resolve_jwplyr") as mock_jw:
        mock_jw.return_value = {
            "id": "mock_id",
            "title": "Mock Video Title",
            "stream_url": "https://example.com/stream.mp4",
            "thumbnail": "https://example.com/thumb.jpg",
            "platform": "jwplyr",
            "headers": {"Referer": "https://jwplyr.com/"}
        }
        res = media_extractor.inspect_url("https://jwplyr.com/e/mock_id")
        assert res["title"] == "Mock Video Title"
        assert res["platform"] == "jwplyr"
        assert res["formats"][0]["resolution"] == "Original Stream (MP4/HLS)"


def test_telegram_status_endpoint():
    res = client.get("/api/v1/telegram/status")
    assert res.status_code == 200
    assert "configured" in res.json()


def test_telegram_config_validation():
    # Empty token rejected
    res = client.post("/api/v1/telegram/config", json={"bot_token": "", "chat_id": ""})
    assert res.status_code == 400

    # Valid mock token
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": {"username": "MockBot", "first_name": "Mock"}}
        mock_get.return_value = mock_resp

        res_ok = client.post("/api/v1/telegram/config", json={"bot_token": "123:ABC", "chat_id": "999"})
        assert res_ok.status_code == 200
        assert res_ok.json()["bot_username"] == "MockBot"


def test_telegram_send_without_config_raises_error():
    from app.engine.telegram_relay import telegram_relay
    from app.core.config import settings

    orig_token = telegram_relay.bot_token
    orig_chat = telegram_relay.chat_id
    orig_cfg_token = settings.TELEGRAM_BOT_TOKEN
    orig_cfg_chat = settings.TELEGRAM_CHAT_ID

    telegram_relay.bot_token = ""
    telegram_relay.chat_id = ""
    settings.TELEGRAM_BOT_TOKEN = None
    settings.TELEGRAM_CHAT_ID = None

    try:
        res = client.post("/api/v1/telegram/send", json={"url": "https://example.com/vid", "format_type": "720p"})
        assert res.status_code == 400
        assert "Telegram" in res.json()["detail"]
    finally:
        telegram_relay.bot_token = orig_token
        telegram_relay.chat_id = orig_chat
        settings.TELEGRAM_BOT_TOKEN = orig_cfg_token
        settings.TELEGRAM_CHAT_ID = orig_cfg_chat


def test_telegram_split_video_for_small_file(tmp_path):
    from app.engine.telegram_relay import telegram_relay
    fake_file = tmp_path / "small_test.mp4"
    fake_file.write_bytes(b"0" * (1024 * 1024))  # 1 MB

    parts = telegram_relay.split_video_for_telegram(str(fake_file), target_max_mb=42.0)
    assert len(parts) == 1
    assert parts[0] == str(fake_file)


