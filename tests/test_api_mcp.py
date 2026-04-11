import importlib
import sys


def load_api_module():
    sys.modules.pop("api.mcp", None)
    return importlib.import_module("api.mcp")


def test_mcp_auth_token_is_trimmed(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "  secret-token\n")

    module = load_api_module()

    assert module.MCP_AUTH_TOKEN == "secret-token"


def test_bearer_auth_middleware_trims_passed_token():
    module = load_api_module()

    middleware = module.BearerAuthMiddleware(lambda scope, receive, send: None, "  secret-token\n")

    assert middleware.token == "secret-token"
