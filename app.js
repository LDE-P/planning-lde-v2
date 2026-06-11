// Point d'entrée — init, chargement des données

import { fetchState, getLock } from './api.js';
import { init, renderAll, setFetchStateCallback } from './ui.js';

async function checkLock() {
  try {
    const lock = await getLock();
    const banner = document.getElementById('lock-banner');
    if (!banner) return;
    if (lock.locked) {
      let since = lock.since || '';
      try { since = new Date(lock.since).toLocaleTimeString('fr-FR'); } catch (e) {}
      banner.textContent = `⚠️ Session IA en cours d'édition de data.json (${lock.by} — depuis ${since}) — modifications dashboard déconseillées`;
      banner.style.display = 'flex';
    } else {
      banner.style.display = 'none';
    }
  } catch (e) { /* serveur injoignable — pas de bannière */ }
}

async function main() {
  try {
    const state = await fetchState();
    init(state);
    setFetchStateCallback(fetchState);
    // Vérification verrou initiale + polling toutes les 30s
    checkLock();
    setInterval(checkLock, 30000);
  } catch (err) {
    document.getElementById('loading').textContent = `Erreur : ${err.message}`;
  }
}

main();
