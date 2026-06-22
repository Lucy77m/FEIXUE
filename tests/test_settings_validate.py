"""Tests for Settings.validate()."""
from __future__ import annotations

from desktop_pet.settings import Settings


def test_validate_empty_key():
    s = Settings(api_key="", base_url="https://api.openai.com/v1", model="gpt-4o")
    errors = s.validate()
    assert "api_key_empty" in errors


def test_validate_invalid_url():
    s = Settings(api_key="sk-test", base_url="not-a-url", model="gpt-4o")
    errors = s.validate()
    assert "base_url_invalid" in errors


def test_validate_empty_base_url():
    s = Settings(api_key="sk-test", base_url="", model="gpt-4o")
    errors = s.validate()
    assert "base_url_empty" in errors


def test_validate_empty_model():
    s = Settings(api_key="sk-test", base_url="https://api.openai.com/v1", model="")
    errors = s.validate()
    assert "model_empty" in errors


def test_validate_low_history_tokens():
    s = Settings(api_key="sk-test", base_url="https://api.openai.com/v1", model="gpt-4o", history_tokens=1000)
    errors = s.validate()
    assert "history_tokens_low" in errors


def test_validate_all_valid():
    s = Settings(api_key="sk-test", base_url="https://api.openai.com/v1", model="gpt-4o")
    assert s.validate() == []


def test_validate_accepts_http():
    s = Settings(api_key="sk-test", base_url="http://localhost:8080/v1", model="gpt-4o")
    assert s.validate() == []


def test_validate_multiple_errors():
    s = Settings(api_key="", base_url="bad", model="")
    errors = s.validate()
    assert "api_key_empty" in errors
    assert "base_url_invalid" in errors
    assert "model_empty" in errors
