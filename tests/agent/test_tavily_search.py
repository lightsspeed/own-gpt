"""
Unit tests for Tavily Web Search Tool (V3 Phase 3).

Verifies tool registration, safety bounds, structured results, missing API key
graceful handling, timeout/error handling, and guardrail classification.
"""

import pytest
from app.agent.tools import tools, web_search
from app.agent.tool_impls import web_search_impl
from app.agent.guardrail import check_tool_call, GuardrailAction
from app.core.config import settings


def _set_config(monkeypatch, **kwargs):
    for k, v in kwargs.items():
        monkeypatch.setattr(settings, k, v)


class TestTavilyWebSearchTool:
    def test_web_search_tool_registered(self):
        tool_names = [t.name for t in tools]
        assert "web_search" in tool_names

    def test_guardrail_allows_web_search(self):
        decision = check_tool_call("web_search", {"query": "Kubernetes RBAC"})
        assert decision.action == GuardrailAction.ALLOW

    def test_missing_api_key_fails_gracefully(self, monkeypatch):
        _set_config(monkeypatch, TAVILY_API_KEY="")
        result = web_search_impl("latest tech news")
        assert "TAVILY_API_KEY is not configured" in result
        assert isinstance(result, str)

    def test_empty_query_returns_message(self, monkeypatch):
        _set_config(monkeypatch, TAVILY_API_KEY="tvly-test-key")
        result = web_search_impl("   ")
        assert "query cannot be empty" in result

    def test_successful_search_returns_structured_results(self, monkeypatch):
        _set_config(monkeypatch, TAVILY_API_KEY="tvly-test-key")

        class FakeResponse:
            status_code = 200
            def json(self):
                return {
                    "results": [
                        {
                            "title": "Kubernetes Documentation",
                            "url": "https://kubernetes.io/docs/home/",
                            "content": "Production-Grade Container Orchestration system.",
                        },
                        {
                            "title": "Kubernetes GitHub",
                            "url": "https://github.com/kubernetes/kubernetes",
                            "content": "Production-Grade Container Scheduling and Management.",
                        },
                    ]
                }

        posted_data = {}
        def mock_post(url, json, headers, timeout):
            posted_data["url"] = url
            posted_data["json"] = json
            posted_data["timeout"] = timeout
            return FakeResponse()

        monkeypatch.setattr("requests.post", mock_post)

        result = web_search_impl("kubernetes architecture", max_results=3)

        assert posted_data["url"] == "https://api.tavily.com/search"
        assert posted_data["json"]["query"] == "kubernetes architecture"
        assert posted_data["json"]["max_results"] == 3
        assert posted_data["timeout"] == 10.0

        assert "Title: Kubernetes Documentation" in result
        assert "URL: https://kubernetes.io/docs/home/" in result
        assert "Domain: kubernetes.io" in result
        assert "Snippet: Production-Grade Container Orchestration" in result

    def test_query_length_bounded_to_300(self, monkeypatch):
        _set_config(monkeypatch, TAVILY_API_KEY="tvly-test-key")

        posted_data = {}
        def mock_post(url, json, headers, timeout):
            posted_data["json"] = json
            res = type("R", (), {"status_code": 200, "json": lambda self: {"results": []}})()
            return res

        monkeypatch.setattr("requests.post", mock_post)

        long_query = "A" * 500
        web_search_impl(long_query)

        assert len(posted_data["json"]["query"]) == 300

    def test_max_results_clamped_to_5(self, monkeypatch):
        _set_config(monkeypatch, TAVILY_API_KEY="tvly-test-key")

        posted_data = {}
        def mock_post(url, json, headers, timeout):
            posted_data["json"] = json
            res = type("R", (), {"status_code": 200, "json": lambda self: {"results": []}})()
            return res

        monkeypatch.setattr("requests.post", mock_post)

        web_search_impl("query", max_results=100)

        assert posted_data["json"]["max_results"] == 5

    def test_timeout_handled_gracefully(self, monkeypatch):
        _set_config(monkeypatch, TAVILY_API_KEY="tvly-test-key")

        import requests
        def mock_post(*args, **kwargs):
            raise requests.Timeout("Connection timed out")

        monkeypatch.setattr("requests.post", mock_post)

        result = web_search_impl("slow search")
        assert "timed out after 10 seconds" in result
