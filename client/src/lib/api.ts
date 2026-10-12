export async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`
    );
  }
  return response;
}
