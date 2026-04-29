import React from 'react';
import ReactDOM from 'react-dom/client';
import { IntroSolarSystem } from './IntroSolarSystem.jsx';

function startIntro({ mountId = 'intro-root', onComplete } = {}) {
  const mountEl = document.getElementById(mountId);
  if (!mountEl) {
    // Fail open: if mount is missing, just complete.
    onComplete?.();
    return () => {};
  }

  const root = ReactDOM.createRoot(mountEl);
  root.render(
    <IntroSolarSystem
      onComplete={() => {
        onComplete?.();
      }}
    />,
  );

  return () => {
    try {
      root.unmount();
    } catch {
      // ignore
    }
  };
}

// Expose a stable API for `app/static/scripts/main.js`.
window.pvIntro = { startIntro };

