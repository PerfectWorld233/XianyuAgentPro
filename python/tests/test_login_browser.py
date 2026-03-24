import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from login_browser import _extract_cookie_str


def test_filters_relevant_domains():
    cookies = [
        {"name": "unb", "value": "12345", "domain": ".goofish.com"},
        {"name": "_m_h5_tk", "value": "abc_123", "domain": "h5api.m.goofish.com"},
        {"name": "irrelevant", "value": "xyz", "domain": "example.com"},
        {"name": "sgcookie", "value": "E1abc", "domain": ".taobao.com"},
    ]
    result = _extract_cookie_str(cookies)
    assert "unb=12345" in result
    assert "_m_h5_tk=abc_123" in result
    assert "sgcookie=E1abc" in result
    assert "irrelevant" not in result


def test_empty_cookies():
    assert _extract_cookie_str([]) == ""


def test_no_relevant_domains():
    cookies = [{"name": "foo", "value": "bar", "domain": "example.com"}]
    assert _extract_cookie_str(cookies) == ""
