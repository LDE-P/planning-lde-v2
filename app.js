// Point d'entrée — init, chargement des données

import { fetchState } from './api.js';
import { init, renderAll, setFetchStateCallback } from './ui.js';

async function main() {
  try {
    const state = await fetchState();
    init(state);
    setFetchStateCallback(fetchState);
  } catch (err) {
    document.getElementById('loading').textContent = `Erreur : ${err.message}`;
  }
}

main();
