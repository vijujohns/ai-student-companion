import { apiFetch, parseApiError } from "./api";

export async function fetchAdminOverview() {
  const res = await apiFetch("/admin/overview", { method: "GET" });
  if (!res.ok) {
    throw new Error(await parseApiError(res, "Unable to load admin overview."));
  }
  return res.json();
}

export async function fetchAdminModelProfiles() {
  const res = await apiFetch("/admin/model-profiles", { method: "GET" });
  if (!res.ok) {
    throw new Error(await parseApiError(res, "Unable to load global model profile settings."));
  }
  return res.json();
}

export async function updateAdminModelProfile(profileKey) {
  const res = await apiFetch("/admin/model-profiles", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_key: profileKey }),
  });
  if (!res.ok) {
    throw new Error(await parseApiError(res, "Unable to update the global model profile."));
  }
  return res.json();
}
