/**
 * Kaf Extract JavaScript/TypeScript SDK.
 *
 * @example
 * ```ts
 * import { KafExtract } from "kaf-extract";
 *
 * const client = new KafExtract({ apiKey: "kaf_xxxx" });
 * const result = await client.extract("https://example.com", {
 *   fields: [{ name: "title", selector: "h1", type: "text" }],
 * });
 * console.log(result.data?.title);
 * ```
 */

// ── Types ─────────────────────────────────────────────────────────

export interface FieldSchema {
  name: string;
  selector?: string;
  type?: "text" | "html" | "attribute" | "exists" | "markdown" | "screenshot" | "ai";
  attribute?: string;
  instruction?: string;
}

export interface ExtractSchema {
  fields: FieldSchema[];
  base_selector?: string;
}

export interface ExtractRequest {
  url: string;
  schema: ExtractSchema;
  webhook_url?: string;
}

export interface BatchExtractRequest {
  urls: string[];
  schema: ExtractSchema;
  webhook_url?: string;
}

export interface AIExtractRequest {
  url: string;
  instruction: string;
  model?: string;
  format?: "json" | "text";
}

export interface ScreenshotRequest {
  url: string;
  full_page?: boolean;
  selector?: string;
}

export interface ExtractMetadata {
  url: string;
  duration_ms: number;
  timestamp: string;
}

export interface ExtractResponse {
  status: string;
  data?: Record<string, unknown>;
  metadata?: ExtractMetadata;
}

export interface BatchResult {
  url: string;
  status: string;
  data?: Record<string, unknown>;
  error?: string;
}

export interface BatchExtractResponse {
  results: BatchResult[];
  total: number;
  succeeded: number;
  failed: number;
}

export interface ScreenshotData {
  screenshot: string; // base64-encoded PNG
  format: string;
}

export interface ScreenshotResponse {
  status: string;
  data?: ScreenshotData;
  metadata?: ExtractMetadata;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  name?: string;
  role: string;
  status: string;
  created_at: string;
}

export interface ClientOptions {
  apiKey?: string;
  baseUrl?: string;
  timeout?: number;
}

// ── Error ─────────────────────────────────────────────────────────

export class KafExtractError extends Error {
  statusCode: number;
  response: unknown;

  constructor(message: string, statusCode = 0, response: unknown = null) {
    super(message);
    this.name = "KafExtractError";
    this.statusCode = statusCode;
    this.response = response;
  }
}

// ── Client ────────────────────────────────────────────────────────

export class KafExtract {
  private apiKey?: string;
  private baseUrl: string;
  private timeout: number;
  private accessToken?: string;

  constructor(options: ClientOptions = {}) {
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl || "https://extract.kafcenter.com").replace(
      /\/$/,
      ""
    );
    this.timeout = options.timeout || 60_000;
  }

  private get headers(): Record<string, string> {
    const h: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.apiKey) h["X-API-Key"] = this.apiKey;
    if (this.accessToken) h["Authorization"] = `Bearer ${this.accessToken}`;
    return h;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    params?: Record<string, string>
  ): Promise<T> {
    const url = new URL(path, this.baseUrl);
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const res = await fetch(url.toString(), {
        method,
        headers: this.headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!res.ok) {
        let detail: string;
        try {
          const json = await res.json();
          detail = json.detail || JSON.stringify(json);
        } catch {
          detail = await res.text();
        }
        throw new KafExtractError(
          `HTTP ${res.status}: ${detail}`,
          res.status,
          detail
        );
      }

      return (await res.json()) as T;
    } finally {
      clearTimeout(timer);
    }
  }

  // ── Auth ─────────────────────────────────────────────────────

  async register(
    email: string,
    password: string,
    name?: string
  ): Promise<TokenResponse> {
    return this.request<TokenResponse>("POST", "/auth/register", {
      email,
      password,
      name,
    });
  }

  async login(email: string, password: string): Promise<TokenResponse> {
    const data = await this.request<TokenResponse>("POST", "/auth/login", {
      email,
      password,
    });
    this.accessToken = data.access_token;
    return data;
  }

  async me(): Promise<UserResponse> {
    return this.request<UserResponse>("GET", "/auth/me");
  }

  async changePassword(
    currentPassword: string,
    newPassword: string
  ): Promise<{ message: string }> {
    return this.request<{ message: string }>("PUT", "/auth/me/password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }

  // ── Core Extraction ──────────────────────────────────────────

  async extract(
    url: string,
    options: {
      fields: FieldSchema[];
      baseSelector?: string;
      webhookUrl?: string;
      async?: boolean;
      format?: "csv" | "markdown";
    }
  ): Promise<ExtractResponse> {
    const params: Record<string, string> = {};
    if (options.async) params["async"] = "true";

    return this.request<ExtractResponse>(
      "POST",
      "/api/v1/extract",
      {
        url,
        schema: {
          fields: options.fields,
          base_selector: options.baseSelector,
        },
        webhook_url: options.webhookUrl,
      },
      params
    );
  }

  async extractBatch(
    urls: string[],
    options: {
      fields: FieldSchema[];
      baseSelector?: string;
      webhookUrl?: string;
      async?: boolean;
    }
  ): Promise<BatchExtractResponse> {
    const params: Record<string, string> = {};
    if (options.async) params["async"] = "true";

    return this.request<BatchExtractResponse>(
      "POST",
      "/api/v1/extract/batch",
      {
        urls,
        schema: {
          fields: options.fields,
          base_selector: options.baseSelector,
        },
        webhook_url: options.webhookUrl,
      },
      params
    );
  }

  async getJob(jobId: string): Promise<ExtractResponse> {
    return this.request<ExtractResponse>(
      "GET",
      `/api/v1/extract/${jobId}`
    );
  }

  async extractAI(
    url: string,
    instruction: string,
    model: string = "kimi-k2.6:cloud",
    format: "json" | "text" = "json"
  ): Promise<ExtractResponse> {
    return this.request<ExtractResponse>("POST", "/api/v1/extract/ai", {
      url,
      instruction,
      model,
      format,
    });
  }

  async screenshot(
    url: string,
    options?: { fullPage?: boolean; selector?: string }
  ): Promise<ScreenshotResponse> {
    return this.request<ScreenshotResponse>(
      "POST",
      "/api/v1/extract/screenshot",
      {
        url,
        full_page: options?.fullPage ?? false,
        selector: options?.selector,
      }
    );
  }

  // ── Vouchers ─────────────────────────────────────────────────

  async redeemVoucher(code: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(
      "POST",
      "/api/v1/vouchers/redeem",
      { code }
    );
  }

  async voucherHistory(): Promise<Record<string, unknown>[]> {
    return this.request<Record<string, unknown>[]>(
      "GET",
      "/api/v1/vouchers/history"
    );
  }

  // ── Scheduled Extractions ────────────────────────────────────

  async createSchedule(options: {
    name: string;
    cronExpression: string;
    url: string;
    fields: FieldSchema[];
    webhookUrl?: string;
    emailOnComplete?: string;
  }): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(
      "POST",
      "/api/v1/extract/schedule",
      {
        name: options.name,
        cron_expression: options.cronExpression,
        url: options.url,
        fields: options.fields,
        webhook_url: options.webhookUrl,
        email_on_complete: options.emailOnComplete,
      }
    );
  }

  async listSchedules(): Promise<{ schedules: Record<string, unknown>[]; total: number }> {
    return this.request<{ schedules: Record<string, unknown>[]; total: number }>(
      "GET",
      "/api/v1/extract/schedules"
    );
  }

  async getSchedule(scheduleId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(
      "GET",
      `/api/v1/extract/schedule/${scheduleId}`
    );
  }

  async deleteSchedule(scheduleId: string): Promise<void> {
    await this.request<void>(
      "DELETE",
      `/api/v1/extract/schedule/${scheduleId}`
    );
  }

  async pauseSchedule(scheduleId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(
      "POST",
      `/api/v1/extract/schedule/${scheduleId}/pause`
    );
  }

  async resumeSchedule(scheduleId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(
      "POST",
      `/api/v1/extract/schedule/${scheduleId}/resume`
    );
  }

  // ── Health ───────────────────────────────────────────────────

  async health(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("GET", "/health");
  }
}

export default KafExtract;
