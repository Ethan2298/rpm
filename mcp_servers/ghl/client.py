import httpx

from mcp_servers.ghl.config import GHL_API_KEY, GHL_BASE_URL, GHL_API_VERSION, GHL_LOCATION_ID


class GHLAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"GHL API {status_code}: {message}")


class GHLClient:
    def __init__(self):
        if not GHL_API_KEY:
            raise ValueError("GHL_API_KEY environment variable is required")
        if not GHL_LOCATION_ID:
            raise ValueError("GHL_LOCATION_ID environment variable is required")

        self._client = httpx.AsyncClient(
            base_url=GHL_BASE_URL,
            headers={
                "Authorization": f"Bearer {GHL_API_KEY}",
                "Version": GHL_API_VERSION,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )
        self.location_id = GHL_LOCATION_ID

    # GHL's API is inconsistent — some endpoints want locationId (camelCase),
    # others want location_id (snake_case) and reject the other format.
    SNAKE_CASE_ENDPOINTS = {"/opportunities/search"}

    # Sub-resource endpoints that reject locationId in query params (422).
    # These resolve the parent entity by the ID in the path, not by location.
    NO_LOCATION_PATTERNS = {"/notes", "/tasks", "/messages", "/free-slots"}

    def _needs_location(self, path: str) -> bool:
        """Return False for sub-resource paths that reject locationId."""
        for pattern in self.NO_LOCATION_PATTERNS:
            if path.endswith(pattern):
                return False
        return True

    def _inject_location(self, params: dict | None, path: str = "") -> dict:
        params = params or {}
        if not self._needs_location(path):
            return params
        if path in self.SNAKE_CASE_ENDPOINTS:
            if "location_id" not in params:
                params["location_id"] = self.location_id
        else:
            if "locationId" not in params:
                params["locationId"] = self.location_id
        return params

    async def get(self, path: str, params: dict | None = None) -> dict:
        params = self._inject_location(params, path)
        resp = await self._client.get(path, params=params)
        return self._handle_response(resp)

    async def post(self, path: str, json: dict | None = None, params: dict | None = None) -> dict:
        params = self._inject_location(params, path) if params else None
        resp = await self._client.post(path, json=json, params=params)
        return self._handle_response(resp)

    async def put(self, path: str, json: dict | None = None, params: dict | None = None) -> dict:
        params = self._inject_location(params, path) if params else None
        resp = await self._client.put(path, json=json, params=params)
        return self._handle_response(resp)

    async def delete(self, path: str, json: dict | None = None, params: dict | None = None) -> dict:
        params = self._inject_location(params, path) if params else None
        resp = await self._client.request("DELETE", path, json=json, params=params)
        return self._handle_response(resp)

    def _handle_response(self, resp: httpx.Response) -> dict:
        if resp.status_code >= 400:
            try:
                error_data = resp.json()
                message = error_data.get("message", resp.text)
            except Exception:
                message = resp.text

            raise GHLAPIError(resp.status_code, message)

        return resp.json()

    async def close(self):
        await self._client.aclose()
