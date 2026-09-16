import { Hono } from "hono";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
/**
 * Evidence API — serves shipment/vessel/container/port/GPS/inspection/document
 * data in exactly the shape verification_engine/client.py expects:
 *
 *   GET /api/v1/shipments/:id
 *   GET /api/v1/vessels/:imo
 *   GET /api/v1/containers/:number
 *   GET /api/v1/containers/:number/events
 *   GET /api/v1/vessels/:imo/gps
 *   GET /api/v1/shipments/:id/documents
 *   GET /api/v1/shipments/:id/inspections
 *
 * All timestamps in the underlying data file are stored as "offset hours
 * from now" and converted to real ISO timestamps at request time, so the
 * data always looks fresh (passes the DATA_FRESHNESS rule) no matter when
 * you run the demo.
 *
 * Backed by data/evidence-store.json. Two shipment IDs are seeded:
 *   CP-CLEAN  -> everything consistent, engine should return VERIFIED
 *   CP-FRAUD  -> container registered to a different vessel than claimed,
 *                engine should return REJECTED (VESSEL_CONTAINER_MATCH fails)
 */
const __dirname = dirname(fileURLToPath(import.meta.url));
const STORE_PATH = join(__dirname, "..", "..", "data", "evidence-store.json");
function loadStore() {
    const raw = readFileSync(STORE_PATH, "utf-8");
    return JSON.parse(raw);
}
function offsetToIso(hoursAgo) {
    const d = new Date(Date.now() - hoursAgo * 60 * 60 * 1000);
    return d.toISOString();
}
function resolveTimestamps(obj, field, offsetField) {
    if (obj && typeof obj[offsetField] === "number") {
        return { ...obj, [field]: offsetToIso(obj[offsetField]) };
    }
    return obj;
}
export const evidenceApi = new Hono();
evidenceApi.get("/api/v1/shipments/:id", (c) => {
    const store = loadStore();
    const shipment = store.shipments[c.req.param("id")];
    if (!shipment)
        return c.json({ detail: "not found" }, 404);
    return c.json(shipment);
});
evidenceApi.get("/api/v1/vessels/:imo", (c) => {
    const store = loadStore();
    const vessel = store.vessels[c.req.param("imo")];
    if (!vessel)
        return c.json({ detail: "not found" }, 404);
    return c.json(resolveTimestamps(vessel, "last_updated", "last_updated_offset_hours"));
});
evidenceApi.get("/api/v1/containers/:number", (c) => {
    const store = loadStore();
    const container = store.containers[c.req.param("number")];
    if (!container)
        return c.json({ detail: "not found" }, 404);
    return c.json(container);
});
evidenceApi.get("/api/v1/containers/:number/events", (c) => {
    const store = loadStore();
    const events = store.container_events[c.req.param("number")] || [];
    const resolved = events.map((e) => resolveTimestamps(e, "timestamp", "timestamp_offset_hours"));
    return c.json(resolved);
});
evidenceApi.get("/api/v1/vessels/:imo/gps", (c) => {
    const store = loadStore();
    const points = store.gps[c.req.param("imo")] || [];
    const resolved = points.map((p) => resolveTimestamps(p, "timestamp", "timestamp_offset_hours"));
    return c.json(resolved);
});
evidenceApi.get("/api/v1/shipments/:id/documents", (c) => {
    const store = loadStore();
    const docs = store.documents[c.req.param("id")] || [];
    const resolved = docs.map((d) => resolveTimestamps(d, "issued_at", "issued_at_offset_hours"));
    return c.json(resolved);
});
evidenceApi.get("/api/v1/shipments/:id/inspections", (c) => {
    const store = loadStore();
    const inspection = store.inspections[c.req.param("id")];
    if (!inspection)
        return c.json(null, 404);
    return c.json(resolveTimestamps(inspection, "timestamp", "timestamp_offset_hours"));
});
