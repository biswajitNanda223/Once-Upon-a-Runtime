import type { Request } from "express";

export type TrustedIdentity = { externalUserId: string; username: string | null; email: string | null };

function header(request: Request, name: string): string | null {
  const value = request.get(name)?.trim();
  return value || null;
}

export function trustedIdentity(request: Request): TrustedIdentity | null {
  const mode = process.env.AUTH_MODE ?? "databricks";
  if (mode === "local") {
    if (process.env.NODE_ENV === "production") throw new Error("AUTH_MODE=local is forbidden in production");
    return { externalUserId: process.env.LOCAL_USER_ID ?? "local-user-001", username: process.env.LOCAL_USERNAME ?? "Local Director", email: process.env.LOCAL_EMAIL ?? "director@example.test" };
  }
  if (mode !== "databricks") throw new Error(`Unsupported AUTH_MODE: ${mode}`);
  const externalUserId = header(request, "X-Forwarded-User");
  if (!externalUserId) return null;
  return { externalUserId, username: header(request, "X-Forwarded-Preferred-Username"), email: header(request, "X-Forwarded-Email") };
}
