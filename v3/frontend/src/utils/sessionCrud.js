export async function renameScopedSession({
  session,
  endpointPrefix,
  nextTitle,
  setSessions,
  apiFetch,
  parseApiError,
  failureLabel,
}) {
  try {
    const res = await apiFetch(`${endpointPrefix}/${session.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: nextTitle }),
    });
    if (!res.ok) {
      console.error(`❌ Failed to rename ${failureLabel}`, await parseApiError(res, "Rename failed."));
      return false;
    }

    setSessions((prev) =>
      prev.map((item) => (item.id === session.id ? { ...item, title: nextTitle } : item))
    );
    return true;
  } catch (err) {
    console.error(`❌ Rename ${failureLabel} failed:`, err);
    return false;
  }
}

export async function deleteScopedSession({
  session,
  endpointPrefix,
  setSessions,
  apiFetch,
  parseApiError,
  failureLabel,
}) {
  try {
    const res = await apiFetch(`${endpointPrefix}/${session.id}`, { method: "DELETE" });
    if (!res.ok) {
      console.error(`❌ Failed to delete ${failureLabel}`, await parseApiError(res, "Delete failed."));
      return false;
    }

    setSessions((prev) => prev.filter((item) => item.id !== session.id));
    return true;
  } catch (err) {
    console.error(`❌ Delete ${failureLabel} failed:`, err);
    return false;
  }
}