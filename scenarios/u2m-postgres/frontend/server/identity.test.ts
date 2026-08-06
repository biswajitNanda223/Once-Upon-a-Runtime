import { afterEach, describe, expect, it } from "vitest";
import type { Request } from "express";
import { trustedIdentity } from "./identity.js";

const originalEnvironment = { ...process.env };
afterEach(() => { process.env = { ...originalEnvironment }; });

function request(headers: Record<string, string>): Request {
  return { get: (name: string) => headers[name.toLowerCase()] } as Request;
}

describe("trustedIdentity", () => {
  it("reads the gateway identity and ignores body data", () => {
    process.env.AUTH_MODE = "databricks";
    expect(trustedIdentity(request({ "x-forwarded-user": "stable-42", "x-forwarded-email": "new@example.com" }))).toEqual({
      externalUserId: "stable-42",
      username: null,
      email: "new@example.com",
    });
  });

  it("fails closed without the stable header", () => {
    process.env.AUTH_MODE = "databricks";
    expect(trustedIdentity(request({ "x-forwarded-email": "spoof@example.com" }))).toBeNull();
  });

  it("forbids the local adapter in production", () => {
    process.env.AUTH_MODE = "local";
    process.env.NODE_ENV = "production";
    expect(() => trustedIdentity(request({}))).toThrow("forbidden");
  });
});
