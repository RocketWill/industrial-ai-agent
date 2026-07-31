import type { ConversationFetch } from "./conversations";
import { MessageApiError } from "./messages";

export type SyntheticDevice = { id: string; name: string; category: "inspection" | "etch" | "lithography"; data_source: "synthetic_demo" };

function isDevice(value: unknown): value is SyntheticDevice {
  if (typeof value !== "object" || value === null) return false;
  const device = value as SyntheticDevice;
  return typeof device.id === "string" && typeof device.name === "string" && ["inspection", "etch", "lithography"].includes(device.category) && device.data_source === "synthetic_demo";
}

export async function listSyntheticDevices(fetchImplementation: ConversationFetch = fetch): Promise<SyntheticDevice[]> {
  try {
    const base = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, "") || "/api";
    const response = await fetchImplementation(`${base}/devices`, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("unsuccessful response");
    const payload: unknown = await response.json();
    if (!Array.isArray(payload) || !payload.every(isDevice)) throw new Error("invalid response");
    return payload;
  } catch (error) { throw new MessageApiError(error); }
}
