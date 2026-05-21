/**
 * i18n.js — French strings dictionary for BNK.RLVR.CAP.CHN.001.DSH (TASK-002 shell).
 *
 * Minimal for now: empty-state placeholder + error/toast wording. TASK-003
 * will extend with the synthesised-view copy (tier names, envelope category
 * labels, etc.).
 *
 * No third-party i18n library — a plain object keyed by dotted path is
 * sufficient for the volume of strings the shell needs.
 */

export const FR = {
  app: {
    title: 'Tableau de bord',
    subtitle: 'Votre situation, mise à jour en temps réel',
  },

  emptyState: {
    title: 'Première synchronisation en cours…',
    hint: 'Votre tableau de bord apparaîtra dès que vos premières données seront disponibles.',
  },

  consent: {
    title: 'Consentement requis',
    message: 'Pour afficher votre tableau de bord, votre consentement est nécessaire.',
    cta: 'Mettre à jour mon consentement',
    refused: 'Votre consentement a été révoqué.',
  },

  errors: {
    network: 'Connexion indisponible. Nouvelle tentative dans quelques secondes…',
    server: 'Service momentanément indisponible. Réessai en cours…',
    auth: 'Votre session a expiré. Veuillez vous reconnecter.',
    unknown: 'Une erreur inattendue est survenue.',
    fallback: 'Mode démonstration : affichage de données fictives le temps du rétablissement.',
  },

  poll: {
    waiting: 'En attente…',
    ok: 'Synchronisé',
    stale: 'Données potentiellement obsolètes',
    error: 'Synchronisation indisponible',
    fallback: 'Mode démonstration',
  },
};

/**
 * Lookup a dotted path in FR; returns the path itself if the key is missing
 * so that missing translations are visible in the DOM rather than silently
 * yielding `undefined`.
 */
export function t(path, fallback) {
  const parts = path.split('.');
  let cur = FR;
  for (const p of parts) {
    if (cur && typeof cur === 'object' && p in cur) {
      cur = cur[p];
    } else {
      return fallback != null ? fallback : path;
    }
  }
  return typeof cur === 'string' ? cur : (fallback != null ? fallback : path);
}
