import { createHmac, randomUUID } from "node:crypto";
import type { TrustedIdentity } from "./identity.js";

type Token = { access_token: string; expires_in: number };
type AppDetails = { url?: string; status?: { url?: string } };
let cachedToken: { value: string; expiresAt: number } | null = null;
let cachedBackendUrl: string | null = null;

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required`);
  return value.replace(/\/$/, "");
}

async function appToken(): Promise<string> {
  if (cachedToken && cachedToken.expiresAt > Date.now()) return cachedToken.value;
  const host = required("DATABRICKS_HOST");
  const clientId = required("DATABRICKS_CLIENT_ID");
  const clientSecret = required("DATABRICKS_CLIENT_SECRET");
  const response = await fetch(`${host}/oidc/v1/token`, {
    method: "POST",
    headers: { Authorization: `Basic ${Buffer.from(`${clientId}:${clientSecret}`).toString("base64")}`, "Content-Type": "application/x-www-form-urlencoded" },
    body: "grant_type=client_credentials&scope=all-apis",
  });
  if (!response.ok) throw new Error(`Databricks OAuth failed (${response.status})`);
  const token = await response.json() as Token;
  cachedToken = { value: token.access_token, expiresAt: Date.now() + Math.max(token.expires_in - 60, 30) * 1000 };
  return token.access_token;
}

async function backendUrl(token: string): Promise<string> {
  const local = process.env.LOCAL_BACKEND_URL?.trim();
  if ((process.env.AUTH_MODE ?? "databricks") === "local" && local) return local.replace(/\/$/, "");
  if (cachedBackendUrl) return cachedBackendUrl;
  const response = await fetch(`${required("DATABRICKS_HOST")}/api/2.0/apps/${encodeURIComponent(required("BACKEND_APP_NAME"))}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error(`Backend App discovery failed (${response.status})`);
  const app = await response.json() as AppDetails;
  const url = app.url ?? app.status?.url;
  if (!url) throw new Error("Backend App has no running URL");
  cachedBackendUrl = url.replace(/\/$/, "");
  return cachedBackendUrl;
}

export async function syncUser(identity: TrustedIdentity): Promise<{ id: string; username: string | null; email: string | null }> {
  const payload = JSON.stringify({ external_user_id: identity.externalUserId, username: identity.username, email: identity.email });
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const signature = createHmac("sha256", required("INTERNAL_IDENTITY_HMAC_SECRET")).update(`${timestamp}.${payload}`).digest("hex");
  const local = (process.env.AUTH_MODE ?? "databricks") === "local";
  const token = local ? "local-development-token" : await appToken();
  const response = await fetch(`${await backendUrl(token)}/api/internal/users/sync`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", "X-Internal-Timestamp": timestamp, "X-Internal-Signature": `sha256=${signature}`, "X-Request-ID": randomUUID() },
    body: payload,
  });
  if (!response.ok) throw new Error(`User synchronization failed (${response.status})`);
  return response.json() as Promise<{ id: string; username: string | null; email: string | null }>;
}
