import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { syncUser } from "./backend-client.js";
import { trustedIdentity } from "./identity.js";

const app = express();
app.disable("x-powered-by");
app.get("/api/health", (_request, response) => response.json({ status: "ok" }));
app.get("/api/me", async (request, response) => {
  try {
    const identity = trustedIdentity(request);
    if (!identity) return response.status(401).json({ detail: "Databricks identity header is missing" });
    const user = await syncUser(identity);
    return response.json(user);
  } catch (error) {
    console.error("profile_sync_failed", { requestId: request.get("X-Request-ID"), error: error instanceof Error ? error.message : "unknown" });
    return response.status(502).json({ detail: "Profile service is unavailable" });
  }
});

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
app.use(express.static(path.join(root, "dist")));
app.get("/{*path}", (_request, response) => response.sendFile(path.join(root, "dist", "index.html")));
app.listen(Number(process.env.DATABRICKS_APP_PORT ?? 8000), "0.0.0.0");
