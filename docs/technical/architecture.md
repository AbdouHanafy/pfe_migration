# Architecture Technique

## Composants

- `src/discovery`
  - Decouverte des VMs (KVM via libvirt) et extraction des metadonnees.
- `src/analysis`
  - Analyse de compatibilite (regles + score).
- `src/conversion`
  - Plan de conversion (formats de disques, bus, reseau).
- `src/migration`
  - Selection de strategie + orchestration (simulation).
- `src/monitoring`
  - Suivi des jobs et reporting.
- `src/api`
  - API REST (FastAPI).

## Flux de donnees

1. Decouverte des VMs via libvirt.
2. Analyse de compatibilite.
3. Construction du plan de conversion.
4. Selection de la strategie (directe, conversion, alternative).
5. Orchestration de la migration et suivi des etapes.
6. Reporting final.

## Alignement avec le cahier de charge

- Decouverte automatique des VMs: implemente pour KVM.
- Analyse de compatibilite: regles heuristiques.
- Classification intelligente: compatible / partiellement_compatible / non_compatible.
- Conversion automatisee: plan de conversion genere.
- Strategie dynamique: selection automatique selon l'analyse.
- Orchestration: simulation et suivi de job.
- Monitoring: statut et etapes en temps reel (simulation).
- Reporting: rapport JSON via API.
