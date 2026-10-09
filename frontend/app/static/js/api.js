async function apiRequest(path, options = {}) {
  const response = await fetch(`/backend${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item) => `${item.loc?.join(".")}: ${item.msg}`).join("; ")
      : payload.detail;
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return payload;
}

