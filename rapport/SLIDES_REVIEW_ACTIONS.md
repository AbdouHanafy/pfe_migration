# Audit Deck - Ce qui manque et quoi ajouter (slide par slide)

Ce document compare ton deck actuel + le PDF `Restitution-1-Migration-VM-vers-OpenShift-Virtualization.pdf`.
Objectif: te donner exactement quoi ajouter pour passer d'un deck "bon" a un deck "expert-ready".

## 1) Ce qui manque globalement (priorite haute)
1. Chiffres reels visibles en slides principales (pas seulement en annexe):
- taux de succes `Analyze/Plan/Migrate`
- temps moyen par etape
- nombre de VMs testees
- nombre d'echecs + causes principales
2. Une slide "decision architecture" plus tranchée:
- pourquoi UPI dans ton contexte
- pourquoi compact 3 masters
- pourquoi fallback local VMware
3. Une slide "preuve de fonctionnement" avec captures:
- health backend
- resultat analyze/plan
- un cas migration (meme partiel) + logs
4. Une slide "limitations connues" avec impact business/technique.
5. Une slide "planning date par date" jusqu'a la soutenance finale.
6. Une conclusion avec message final en 3 phrases (etat actuel, risque, plan ferme).

## 2) Ce qui est potentiellement discutable devant l'expert
1. Slide ressources (minimal/ideal):
- preciser que les valeurs sont "guidelines labo PFE" et dependent de la version OCP + charge CNV.
- eviter de les presenter comme normes officielles Red Hat.
2. Partie ML:
- si tu annonces performance, montrer source + split train/test + metrique principale.
- sinon parler "couverture + utilite decisionnelle" plutot que "accuracy brute".
3. Migration reelle:
- separer clairement "code pret" et "validation cluster complete" pour eviter ambiguite.

## 3) Ajouts proposes slide par slide

## Slide 1 (Titre)
Ajouter:
- "Version du projet / commit" en bas.
- "Environnement de test" (cluster.ocp.pfe.lan, compact UPI).

## Slide 2 (Contexte)
Ajouter:
- 1 phrase de valeur metier: reduction du risque de migration et standardisation du processus.

## Slide 3 (Objectifs restitution)
Ajouter:
- Critere de succes de la restitution 1 (ex: architecture validee + plan P1 valide).

## Slide 4 (Choix UPI)
Ajouter:
- petit tableau "UPI vs IPI" (controle, complexite, valeur PFE, adequation contexte).
- phrase de conclusion: "UPI choisi pour la maitrise des couches critiques migration".

## Slide 5 (Topologie)
Ajouter:
- schema simple des flux: `User PC -> Bastion -> OpenShift`.
- mention explicite des IP deja utilisees.

## Slide 6 (Composants bastion)
Ajouter:
- qui depend de quoi (ex: migration reelle depend de `oc/virtctl/qemu-img` + kubeconfig).

## Slide 7 (Ressources)
Ajouter:
- badge "guideline PFE".
- colonne "Etat reel actuel" pour comparer ideal vs deploye.

## Slide 8 (Prerequis)
Ajouter:
- checklist de validation binaire (OK/KO) a cocher en live.

## Slide 9 (Artefacts)
Ajouter:
- capture de repertoire ignition / commandes executees.

## Slide 10 (Boot noeuds)
Ajouter:
- duree moyenne de cette phase dans ton experience.
- point de controle: "bootstrap-complete atteint / non".

## Slide 11 (Post-install)
Ajouter:
- capture `oc get nodes` + `oc get co`.

## Slide 12 (Installations)
Ajouter:
- clarifier "ce qui est fait" vs "a faire" avec 2 couleurs.

## Slide 13 (Stockage critique)
Ajouter:
- mini timeline incident -> action -> resultat.
- exemple erreur exacte `unable to locate path for storage pool legacy`.

## Slide 14 (Architecture app)
Ajouter:
- endpoints cles: `/health`, `/analyze`, `/plan`, `/openshift`.

## Slide 15 (ML)
Ajouter:
- inputs exacts (features) et output exact (strategy/confidence/reason).
- condition de fallback heuristique (seuil de confiance).

## Slide 16 (Avancement)
Ajouter:
- un tableau "Module / Etat / Preuve".

## Slide 17 (Difficultes)
Ajouter:
- ligne "impact utilisateur" pour chaque difficulte.

## Slide 18 (Demo)
Ajouter:
- script minute par minute (00:00 -> 05:00).
- plan B si cluster KO (deja mentionne, rendre plus operationnel).

## Slide 19 (Reste a faire)
Ajouter:
- dates cibles (S+1, S+2, S+3).

## Slide 20 (Metriques)
Ajouter:
- valeurs actuelles meme partielles (ne pas laisser vide le jour J).

## Slide 21 (Risques)
Ajouter:
- probabilite + impact + mitigation (format mini risk matrix).

## Slide 22 (Questions expert)
Ajouter:
- "decision attendue" par question (ce que tu veux obtenir concretement).

## Slide 23 (Annexes)
Ajouter:
- lien vers repo/doc exact (chemins locaux ou commits).

## Slide 24 (Backup demo)
Ajouter:
- captures prechargees numerotees (B1, B2, B3) pour enchainement rapide.

## 4) Slides supplementaires recommandees (a ajouter)

## Nouvelle slide A - Resultats chiffres actuels
Contenu:
- Nb VMs testees
- Taux succes Analyze
- Taux succes Plan
- Taux succes Migrate (ou "en cours")
- Temps moyen par etape
But:
- Donner une preuve objective de progression.

## Nouvelle slide B - Cas reel "devops" (etude de cas)
Contenu:
- contexte VM (taille, split vmdk, source)
- probleme rencontre
- correction appliquee
- resultat
But:
- Montrer ta capacite a resoudre un vrai cas terrain.

## Nouvelle slide C - Planning jusqu'a soutenance (date par date)
Contenu:
- jalons hebdomadaires
- livrables associes
- critere Done pour chaque jalon
But:
- Rassurer l'expert sur la maitrise du reste a faire.

## Nouvelle slide D - Decisions attendues de l'expert
Contenu:
- 3 decisions a prendre aujourd'hui
- impact de chaque decision sur le planning
But:
- Transformer la reunion en validation actionnable.

## 5) Texte court de conclusion (pret a dire)
"La base applicative est stable et le pipeline Discover/Analyze/Plan est operationnel.
Le principal risque restant est infra, surtout le stockage OpenShift pour la migration reelle.
Avec la validation des choix architecture et stockage aujourd'hui, la finalisation end-to-end est realiste dans le prochain jalon."

## 6) Checklist finale avant presentation
- Remplir toutes les valeurs `A_COMPLETER`.
- Mettre 3 captures minimum (analyze, plan, cluster status).
- Preparer 1 demo live + 1 scenario fallback.
- Verifier coherence date/commit/environnement.
- Repetition orale 2 fois (15 min max).
