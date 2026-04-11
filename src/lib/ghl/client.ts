const GHL_BASE_URL = "https://services.leadconnectorhq.com";
const GHL_API_VERSION = "2021-07-28";

export class GHLAPIError extends Error {
  constructor(
    public statusCode: number,
    public override message: string,
  ) {
    super(`GHL API ${statusCode}: ${message}`);
    this.name = "GHLAPIError";
  }
}

class GHLClient {
  private apiKey: string;
  private locationId: string;

  constructor() {
    const apiKey = process.env.GHL_API_KEY?.trim();
    const locationId = process.env.GHL_LOCATION_ID?.trim();
    if (!apiKey) throw new Error("GHL_API_KEY environment variable is required");
    if (!locationId)
      throw new Error("GHL_LOCATION_ID environment variable is required");
    this.apiKey = apiKey;
    this.locationId = locationId;
  }

  private get headers(): Record<string, string> {
    return {
      Authorization: `Bearer ${this.apiKey}`,
      Version: GHL_API_VERSION,
      "Content-Type": "application/json",
      Accept: "application/json",
    };
  }

  private injectLocation(params: Record<string, string>): Record<string, string> {
    if (!params.locationId) {
      params.locationId = this.locationId;
    }
    return params;
  }

  private buildUrl(path: string, params?: Record<string, string>): string {
    const url = new URL(path, GHL_BASE_URL);
    if (params) {
      const injected = this.injectLocation({ ...params });
      for (const [key, value] of Object.entries(injected)) {
        if (value !== undefined && value !== "") {
          url.searchParams.set(key, value);
        }
      }
    } else {
      url.searchParams.set("locationId", this.locationId);
    }
    return url.toString();
  }

  private async handleResponse(resp: Response): Promise<Record<string, unknown>> {
    if (resp.status >= 400) {
      let message: string;
      try {
        const errorData = await resp.json();
        message = (errorData as Record<string, string>).message || resp.statusText;
      } catch {
        message = resp.statusText;
      }

      if (resp.status === 401) {
        message += ". Check that the required scope is enabled on the GHL Private Integration Token.";
      } else if (resp.status === 403) {
        message += ". The PIT token may not have access to this location or resource.";
      }

      throw new GHLAPIError(resp.status, message);
    }

    return resp.json() as Promise<Record<string, unknown>>;
  }

  async get(path: string, params?: Record<string, string>): Promise<Record<string, unknown>> {
    const url = this.buildUrl(path, params);
    const resp = await fetch(url, { headers: this.headers });
    return this.handleResponse(resp);
  }

  async post(
    path: string,
    body?: Record<string, unknown>,
    params?: Record<string, string>,
  ): Promise<Record<string, unknown>> {
    const url = this.buildUrl(path, params);
    const resp = await fetch(url, {
      method: "POST",
      headers: this.headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    return this.handleResponse(resp);
  }

  async put(
    path: string,
    body?: Record<string, unknown>,
    params?: Record<string, string>,
  ): Promise<Record<string, unknown>> {
    const url = this.buildUrl(path, params);
    const resp = await fetch(url, {
      method: "PUT",
      headers: this.headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    return this.handleResponse(resp);
  }

  async delete(
    path: string,
    body?: Record<string, unknown>,
    params?: Record<string, string>,
  ): Promise<Record<string, unknown>> {
    const url = this.buildUrl(path, params);
    const resp = await fetch(url, {
      method: "DELETE",
      headers: this.headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    return this.handleResponse(resp);
  }

  getLocationId(): string {
    return this.locationId;
  }
}

let _client: GHLClient | null = null;

export function getGHLClient(): GHLClient {
  if (!_client) {
    _client = new GHLClient();
  }
  return _client;
}
