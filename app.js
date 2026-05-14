// Point d'entrée — init, chargement des données

import { fetchState, fetchGsheetStatus } from './api.js';
import { init, renderAll, updateGsheetStatus } from './ui.js';

async function main() {
  try {
    const state = await fetchState();
    init(state);

    fetchGsheetStatus()
      .then(r => updateGsheetStatus(r.connected))
      .catch(() => updateGsheetStatus(false));
  } catch (err) {
    document.getElementById('loading').textContent = `Erreur : ${err.message}`;
  }
}

main();
