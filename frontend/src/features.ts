import { useEffect, useState } from 'react';

export interface Features {
  ai: boolean; // Gemini key configured
  factcheck: boolean; // Google Fact Check key configured
}

export const AI_DISABLED_HINT = 'AI is off: add GPS_GEMINI_API_KEY to backend/.env and restart the backend.';

// Fetched once per page load and shared; assumes "on" until known so buttons don't flash disabled.
let cached: Promise<Features> | null = null;

export function useFeatures(): Features {
  const [features, setFeatures] = useState<Features>({ ai: true, factcheck: true });
  useEffect(() => {
    cached ??= fetch('/api/health/features')
      .then((r) => (r.ok ? r.json() : { ai: true, factcheck: true }))
      .catch(() => ({ ai: true, factcheck: true }));
    let live = true;
    cached.then((f) => live && setFeatures(f));
    return () => {
      live = false;
    };
  }, []);
  return features;
}
