export async function fetchPresets() {
  const response = await fetch('/api/presets');
  if (!response.ok) throw new Error(`Presets request failed (${response.status})`);
  return response.json();
}

export async function fetchBaseline(payload) {
  const response = await fetch('/api/baseline', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return response.json();
}

export async function fetchYield(payload) {
  const response = await fetch('/api/yield', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return response.json();
}