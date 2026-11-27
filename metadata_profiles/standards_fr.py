# metadata_profiles/standards_fr.py
#
# French text for the "Metadata Standard Info" dialog. Mirrors the structure
# of STANDARDS_REGISTRY (same contexts, same number of covered/not_covered
# items, same order); URLs and the English registry are the source of truth,
# only the human-readable strings are overridden. A context or key missing
# here falls back to English.

STANDARDS_FR = {
    "Microscopy": {
        "standard_name": "REMBI (Recommended Metadata for Biological Images — métadonnées recommandées pour les images biologiques)",
        "secondary_label": "BioImage Archive — guide REMBI",
        "covered": [
            "Acquisition de l'image : objectif, ouverture numérique, grossissement, "
            "microscope, détecteur, source lumineuse, noms des canaux et temps "
            "d'exposition, taille de pixel, dimensions de l'image, profondeur de "
            "bits, heure d'acquisition.",
        ],
        "not_covered": [
            "Échantillon biologique (organisme, souche, génotype, conditions de "
            "culture) : non intégré par le logiciel d'acquisition; à fournir "
            "séparément.",
            "Spécimen (fixation, coloration, inclusion, coupe) : même remarque "
            "que ci-dessus.",
            "Analyse d'image (méthode de segmentation, logiciel, paramètres) : "
            "présente seulement si le logiciel d'analyse l'a écrite dans le fichier.",
        ],
    },
    "Microscopy (OME)": {
        "standard_name": "OME-XML / OME-TIFF",
        "secondary_label": "Spécification du modèle de données OME",
        "covered": [
            "Élément Pixels : dimensions, taille physique du pixel et unités, "
            "type de pixel.",
            "Éléments Channel : nom, échantillons par pixel, type d'illumination.",
            "Instrument/Objectif : modèle, grossissement, ouverture numérique, "
            "immersion, correction.",
        ],
        "not_covered": [
            "StructuredAnnotations (notes libres sur l'expérience) : analysées "
            "seulement si présentes; tous les exportateurs OME-TIFF ne les "
            "renseignent pas.",
            "Champs d'échantillon biologique et de spécimen, même remarque que "
            "pour REMBI ci-dessus.",
        ],
    },
    "Remote Sensing": {
        "standard_name": "ISO 19115 (Information géographique — Métadonnées)",
        "secondary_label": "FGDC — aperçu des métadonnées géospatiales ISO",
        "covered": [
            "Référence spatiale : SCR (code EPSG, WKT), boîte englobante, "
            "résolution des pixels, nombre et descriptions des bandes, valeur "
            "« sans données », type de données des bandes, interprétation des "
            "pixels (surface ou point, lorsqu'elle est définie).",
        ],
        "not_covered": [
            "Lignée/provenance (historique de traitement), distribution et "
            "parties responsables : catégories d'ISO 19115 absentes des balises "
            "GeoTIFF brutes; elles sont généralement fournies par un fichier .xml "
            "associé ou une fiche de catalogue (p. ex. les outils de métadonnées "
            "de QGIS/ArcGIS).",
        ],
    },
    "General / EXIF": {
        "standard_name": "EXIF (CIPA DC-008) + métadonnées photo IPTC",
        "secondary_label": "Spécification CIPA DC-008 (EXIF 2.32)",
        "covered": [
            "EXIF : marque et modèle de l'appareil, logiciel, date d'acquisition, "
            "résolution, GPS.",
            "IPTC IIM : légende, mots-clés, signature/crédit, avis de droit "
            "d'auteur, lieu (ville/province/pays), instructions spéciales. "
            "JPEG seulement — voir la note ci-dessous.",
            "XMP : conditions d'utilisation / énoncé des droits, mots-clés du "
            "sujet (lorsqu'ils sont présents). JPEG seulement — voir la note "
            "ci-dessous.",
        ],
        "not_covered": [
            "Classification par vocabulaire contrôlé (p. ex. AAT, LCSH) : les "
            "mots-clés IPTC sont du texte libre saisi par le photographe ou "
            "l'archiviste.",
            "IPTC et XMP pour TIFF : l'analyseur TIFF de cette application ne "
            "lit que les balises TIFF de base (les champs équivalents à EXIF : "
            "date, artiste, droit d'auteur, marque/modèle, résolution). Les "
            "blocs IPTC IIM et XMP ne sont analysés que pour les JPEG; les "
            "données IPTC/XMP d'un TIFF, le cas échéant, ne sont pas extraites.",
        ],
    },
    "Neuroimaging (BIDS)": {
        "standard_name": "BIDS 1.9.0 (Brain Imaging Data Structure) — IRM, avec NIfTI-1 et ARRIVE 2.0",
        "secondary_label": "Spécification de l'en-tête NIfTI-1 (voir aussi : lignes directrices ARRIVE 2.0, arriveguidelines.org)",
        "covered": [
            "Géométrie de l'image d'après l'en-tête NIfTI : taille de la matrice, "
            "taille et unités des voxels, nombre de volumes et pas de temps, "
            "type de données, orientation, codes qform/sform. En-tête seulement — "
            "les données de voxels ne sont jamais lues.",
            "Entités du nom de fichier BIDS (sub, ses, task, dir) et suffixe "
            "(T2w, dwi, bold); dossier de type de données (anat, dwi, func).",
            "Paramètres d'acquisition du fichier JSON associé (avec héritage "
            "BIDS) : scanneur, intensité du champ, séquence, TE/TR, angle de "
            "bascule, encodage de phase, temps de lecture, synchronisation des "
            "coupes, tâche.",
            "Gradients de diffusion : valeurs b et nombre de volumes b=0 tirés "
            "de .bval/.bvec.",
            "Contexte du jeu de données : dataset_description.json (nom, version "
            "de BIDS, licence, auteurs, DOI) et noms des colonnes de "
            "participants.tsv.",
            "Suggestions : licence/auteurs/DOI manquants, texte modèle ou "
            "marqueurs de conversion non résolus, champs obligatoires du fichier "
            "associé manquants pour ce type d'image, descripteurs d'animaux "
            "manquants et sform absent.",
        ],
        "not_covered": [
            "Détails de l'étude animale (espèce, souche, sexe, âge, modèle de "
            "lésion, anesthésie, répartition en groupes) : BIDS n'a pas "
            "d'extension pour l'IRM du petit animal et les scanneurs ne les "
            "intègrent pas. Ajoutez-les à participants.tsv et suivez ARRIVE 2.0.",
            "Les valeurs de participants.tsv ne sont volontairement pas lues "
            "(elles peuvent contenir des données démographiques humaines); seuls "
            "les noms de colonnes sont rapportés.",
            "Validation complète de BIDS (toutes les règles d'entités et de "
            "nommage, cohérence entre fichiers) : utilisez le bids-validator "
            "officiel. Cette application signale les lacunes de métadonnées sur "
            "lesquelles un conservateur peut agir.",
            "Données de voxels : statistiques d'image, mouvement ou mesures de "
            "qualité du rapport signal/bruit (utilisez MRIQC) dépassent cette "
            "inspection limitée à l'en-tête.",
        ],
    },
    "Microscopy (OME-Zarr)": {
        "standard_name": "OME-NGFF 0.4 (OME-Zarr) avec BIDS Microscopy (BEP031) et REMBI",
        "secondary_label": "Spécification BIDS Microscopy (voir aussi : REMBI, doi:10.1038/s41592-021-01166-8)",
        "covered": [
            "OME-NGFF : axes (noms, types, unités), niveaux de la pyramide "
            "multi-échelle, transformations d'échelle (taille de pixel normalisée "
            "en µm), étiquettes des canaux (omero), forme des tableaux, découpage "
            "en blocs, type de données, compression. Les métadonnées Zarr v2 et "
            "v3 sont toutes deux lues.",
            "Fichier JSON associé de BIDS Microscopy : taille de pixel acquise et "
            "unités, grossissement, ouverture numérique, immersion, modèle de "
            "l'instrument, logiciel d'acquisition.",
            "Facteur de sous-échantillonnage entre la taille de pixel acquise "
            "(fichier associé) et le niveau de pyramide stocké.",
            "Contexte du jeu de données : dataset_description.json, colonnes de "
            "samples.tsv, logiciel de conversion (GeneratedBy). Fonctionne sur un "
            "dossier .zarr ou directement dans un .tar BIDS non compressé, sans "
            "l'extraire.",
            "Suggestions : dataset_description de type modèle, champs obligatoires "
            "du fichier associé manquants, informations REMBI sur l'échantillon "
            "biologique et le spécimen manquantes, canaux sans nom, axes sans "
            "unités.",
        ],
        "not_covered": [
            "Échantillon biologique et spécimen (REMBI) : organisme, souche, "
            "génotype, traitement/groupe, protocole de clarification, anticorps/"
            "rapporteurs ne sont pas stockés dans l'image; à fournir dans "
            "samples.tsv/samples.json ou dans le dossier de l'étude.",
            "Excitation/émission par canal : les fichiers associés de la "
            "microscopie à feuillet de lumière ne portent souvent qu'une paire de "
            "longueurs d'onde pour une image multicanal; elle est alors omise "
            "plutôt qu'attribuée au mauvais canal.",
            "Valeurs de pixels et niveaux de pyramide non déposés (seuls les "
            "niveaux énumérés dans les métadonnées existent dans le fichier).",
            "Étiquettes/segmentation (labels OME-NGFF), plaques/puits et "
            "transformations autres que l'échelle.",
        ],
    },
    "Micro-CT (Scanco)": {
        "standard_name": "REMBI (Recommended Metadata for Biological Images) — micro-TDM Scanco (AIM)",
        "secondary_label": "BioImage Archive — guide REMBI",
        "covered": [
            "Acquisition de l'image : taille des voxels et de la matrice, étendue "
            "physique, type de voxel, tension et courant du tube à rayons X, temps "
            "d'intégration, projections, codes du type et de l'ID du scanneur, "
            "date d'acquisition, fichier de balayage source, étalonnage (unité de "
            "densité, pente/ordonnée à l'origine, mise à l'échelle de µ). Les deux "
            "versions d'AIM sont lues (020 et la version 030 en 64 bits utilisée "
            "au-delà de 2 Go). En-tête seulement — les données de voxels ne sont "
            "jamais lues.",
            "Analyse d'image : la chaîne de traitement consignée dans le journal "
            "AIM et, pour les fichiers de segmentation, le filtre gaussien et les "
            "valeurs de seuil (en unités de densité), ainsi que le lien vers le "
            "volume parent en niveaux de gris.",
            "Fichiers associés : la sortie d'en-tête .txt (comparée à l'en-tête "
            "AIM) et le script Amira/Avizo .hx (fichier cible, taille de la "
            "matrice et décalage de l'en-tête vérifiés par rapport au volume).",
            "Suggestions : fichiers tronqués, scripts Amira qui pointent vers un "
            "fichier manquant ou dont la casse diffère, instrument identifié "
            "seulement par des codes, informations sur l'échantillon biologique et "
            "le spécimen manquantes.",
        ],
        "not_covered": [
            "Échantillon biologique et spécimen (espèce, site/date de collecte, "
            "fixation, entreposage, coloration) : les fichiers AIM ne contiennent "
            "qu'une étiquette de balayage en texte libre; à fournir dans le README "
            "ou le dossier de l'étude.",
            "Marque/modèle de l'instrument : le scanneur n'est identifié que par "
            "des codes numériques (les tables de codes ne sont pas publiées dans "
            "le fichier).",
            "Valeurs de voxels : histogrammes, volume osseux/tissulaire ou mesures "
            "de densité dépassent cette inspection limitée à l'en-tête; les "
            "statistiques rapportées proviennent du journal de traitement du "
            "fichier lui-même.",
            "Segmentations : seule la taille de l'avant-plan (voxels, mm³, % de la "
            "matrice) est calculée à partir du bloc à longueurs de plage. Le "
            "décompte par objet, le volume tissulaire nécessaire au BV/TV et la "
            "morphométrie relèvent de l'analyse, non des métadonnées, et sont "
            "laissés au logiciel d'analyse.",
        ],
    },
    "Cryo-EM": {
        "standard_name": "MRC2014 / EMPIAR / REMBI — cryo-EM (Thermo Fisher EPU)",
        "secondary_label": "EMPIAR — exigences de dépôt",
        "covered": [
            "Acquisition de l'image : taille de l'image, taille de pixel (Å, vérifiée "
            "entre l'en-tête MRC et le XML EPU), tension d'accélération, grossissement "
            "nominal, défocus appliqué, dose totale (e⁻/Å²), débit de dose, temps "
            "d'exposition, nombre et cadence des images, modèle et numéro de série du "
            "détecteur, comptage d'électrons, fente du filtre en énergie, ouvertures, "
            "microscope et logiciel d'acquisition.",
            "En-tête MRC2014 : mode, ordre des octets, version, type d'en-tête étendu "
            "(FEI1/FEI2) et taille de fichier attendue par rapport à la taille réelle. "
            "Les films EER sont lus à partir de leurs seules étiquettes BigTIFF.",
            "Les fichiers d'une même acquisition (.mrc, _EER.eer, .xml, .jpg) et la "
            "référence de gain nommée dans les métadonnées (recherchée dans le dossier "
            "et ses parents). En-tête seulement — les données d'image ne sont jamais lues.",
            "Suggestions : fichiers tronqués, fichier XML, film ou référence de gain "
            "manquants, écart de taille de pixel, et absence d'information sur le "
            "biospécimen et la préparation du spécimen.",
        ],
        "not_covered": [
            "Biosample et préparation du spécimen (macromolécule, organisme source, "
            "tampon, type de grille, vitrification) : EPU ne les enregistre pas ; "
            "fournissez-les dans le README ou l'entrée EMPIAR.",
            "Qualité de l'image : ajustement de la CTF, mouvement, épaisseur de glace et "
            "nombre de particules sont des résultats de traitement, pas des métadonnées "
            "d'acquisition.",
            "Les valeurs de l'en-tête étendu FEI : le fichier XML contient les mêmes "
            "réglages sous une forme documentée et est utilisé à la place.",
            "Les en-têtes de cartes et demi-cartes EMDB, les séries d'inclinaison de "
            "tomographie et les fichiers associés d'autres fabricants de microscopes.",
        ],
    },
    "Eye Tracking": {
        "standard_name": "Extension BIDS pour l'oculométrie (BEP020) — SR Research EyeLink",
        "secondary_label": "SR Research — assistance EyeLink",
        "covered": [
            "Enregistrement : fréquence d'échantillonnage (en-tête et observée à partir "
            "des horodatages), œil enregistré, méthode de suivi, niveau de filtre, type "
            "d'échantillon, mesure et ajustement de la pupille, modèle du suivi oculaire, "
            "logiciel, caméra et numéro de série.",
            "Affichage : résolution et fréquence de rafraîchissement de l'écran selon le "
            "suivi oculaire, et distance, taille et pixels par degré lorsque le code de "
            "l'expérience les a consignés.",
            "Qualité : type et nombre d'étalonnages, note et erreur de validation "
            "moyenne/maximale (degrés) de la dernière validation, part d'échantillons "
            "manquants, et nombres d'échantillons, de blocs, de fixations, de saccades, de "
            "clignements, d'essais et d'événements d'entrée.",
            "Suggestions : aucune validation, validation médiocre, nombreux échantillons "
            "manquants, fichier tronqué, écart de fréquence, identifiants laissés dans "
            "l'en-tête, géométrie d'écran manquante, absence de l'EDF d'origine. Le "
            "fichier est lu en un seul passage ; les échantillons sont comptés, jamais conservés.",
        ],
        "not_covered": [
            "Descriptions du participant, de la séance, de la tâche et du stimulus : le "
            "fichier ASC n'en contient que ce que le code de l'expérience a consigné "
            "sous forme de messages.",
            "Conversion vers BIDS (_eyetrack.tsv.gz et son fichier .json) : BEP020 est "
            "encore une proposition ; cette application rapporte les champs, elle ne les écrit pas.",
            "Qualité des données du regard au-delà de la validation du suivi oculaire "
            "(précision, perte de données par essai, dérive) : de l'analyse, pas des métadonnées.",
            "Autres suivis oculaires (Tobii, Pupil Labs) et fichiers EDF binaires.",
        ],
    },
    "Vector GIS": {
        "standard_name": "ISO 19115 — Shapefile ESRI et GeoJSON (RFC 7946)",
        "secondary_label": "GeoJSON — RFC 7946",
        "covered": [
            "Système de référence : la définition du .prj (nom, géographique ou projeté, "
            "unité, code EPSG lorsqu'il correspond) pour un shapefile ; le membre « crs » "
            "ou la valeur par défaut WGS 84 pour GeoJSON.",
            "Étendue géographique et représentation spatiale : emprise, type de géométrie, "
            "nombre d'entités, valeurs Z et M.",
            "Description des attributs : noms, types et largeurs des champs d'après "
            "l'en-tête du .dbf, ou noms et types de valeurs des propriétés en GeoJSON ; "
            "encodage du texte d'après le .cpg.",
            "Cohérence : le .shp, le .shx et le .dbf d'un shapefile concordent en taille "
            "et en nombre d'enregistrements, et un .shp et un .geojson de même nom "
            "concordent en étendue. La géométrie d'un shapefile n'est jamais lue.",
            "Suggestions : .shx/.dbf/.prj/.cpg manquants, fichiers tronqués, coordonnées "
            "hors de la plage lon/lat, membre « crs » hérité, fausse précision, nom de "
            "couche différent du nom du fichier, absence de fiche ISO.",
        ],
        "not_covered": [
            "Titre, résumé, généalogie, objectif, contacts et licence (identification et "
            "généalogie ISO 19115) : aucun des deux formats ne peut les contenir ; "
            "fournissez une fiche ISO ou décrivez-les dans le README.",
            "Validité des géométries (auto-intersections, orientation des anneaux, "
            "sommets en double) et topologie : de l'analyse dans un logiciel SIG, pas des métadonnées.",
            "Signification et unités des attributs : les noms de champs sont lus, "
            "leurs définitions ne le sont pas.",
            "GeoPackage, KML, géodatabases fichier et fichiers GeoJSON de plus de 128 Mo.",
        ],
    },
    "Medical Imaging": {
        "standard_name": "DICOM (Digital Imaging and Communications in Medicine)",
        "secondary_label": "DICOM PS3.3 — Définitions des objets d'information",
        "covered": [
            "Contexte d'acquisition : modalité, fabricant/modèle, description de "
            "l'étude et de la série, partie du corps, protocole, espacement des "
            "pixels, épaisseur de coupe.",
        ],
        "not_covered": [
            "Les champs permettant d'identifier le patient sont volontairement "
            "exclus par cette application (PatientName, PatientID, "
            "PatientBirthDate, etc.) — voir metadata_parsers/dicom_parser.py. "
            "Utilisez les outils de dépersonnalisation de votre établissement si "
            "des données au niveau du patient sont nécessaires.",
        ],
    },
    "Microscopy (Leica)": {
        "standard_name": "REMBI (Recommended Metadata for Biological Images) — Leica LIF",
        "secondary_label": "Leica — aperçu du format de fichier LIF",
        "covered": [
            "Acquisition de l'image : nom de l'image, nombre de séries, dimensions "
            "(X/Y/Z/T), nombre de canaux, taille de pixel (µm/pixel en X/Y/Z), "
            "profondeur de bits par canal.",
            "Optique : ouverture numérique, grossissement, nom de l'objectif, zoom "
            "numérique, taille du sténopé (tirés du bloc "
            "ATLConfocalSettingDefinition).",
            "Mosaïque : nombre et positions des tuiles (lorsqu'elles sont "
            "présentes).",
        ],
        "not_covered": [
            "Noms des canaux et longueurs d'onde d'excitation/émission — stockés "
            "dans un bloc XML distinct que readlif n'analyse pas encore; utilisez "
            "Fiji/Bio-Formats pour obtenir toutes les métadonnées des canaux.",
            "Date/heure d'acquisition — pas intégrée de façon constante dans le "
            "XML des LIF.",
            "Champs d'échantillon biologique et de spécimen — même remarque que "
            "pour REMBI/TIFF ci-dessus.",
        ],
    },
    "General / HDF5": {
        "standard_name": "HDF5 (Hierarchical Data Format, version 5)",
        "secondary_label": "Documentation de h5py",
        "covered": [
            "Structure du conteneur : groupes, jeux de données, dimensions, types "
            "de données, filtres de compression (gzip, szip, lzf, etc.).",
            "Attributs globaux au niveau racine (p. ex. Conventions, institution).",
            "Noms des attributs de chaque jeu de données (jusqu'à 5 par jeu).",
            "Indicateurs de risque de curation : EXTERNAL_LINK, "
            "PROPRIETARY_COMPRESSION, NOT_SELF_DESCRIBING.",
        ],
        "not_covered": [
            "Sémantique propre à un domaine (ce que représentent les jeux de "
            "données) — HDF5 est un conteneur générique; le sens des champs "
            "dépend des conventions de la communauté scientifique (p. ex. les "
            "conventions CF pour les sciences du climat et de la Terre, OME-Zarr "
            "pour la bio-imagerie).",
            "Valeurs complètes des attributs de chaque jeu de données — seuls les "
            "noms sont listés pour ne pas alourdir le rapport.",
        ],
    },
    "Remote Sensing (NetCDF)": {
        "standard_name": "ISO 19115 (Information géographique — Métadonnées) via les conventions CF",
        "secondary_label": "Conventions CF pour les métadonnées climatiques et de prévision",
        "covered": [
            "Attributs globaux : version des conventions, établissement, titre, "
            "historique de traitement, source.",
            "Inventaire des dimensions et des variables : nom, forme, type de "
            "données, unités, long_name, standard_name.",
            "Variables de coordonnées (lat/lon/temps/profondeur/niveau) lorsqu'elles "
            "portent des noms conformes aux conventions CF.",
        ],
        "not_covered": [
            "Détails de la référence spatiale (SCR, boîte englobante, résolution "
            "des pixels) comme pour GeoTIFF — NetCDF les stocke dans des variables "
            "grid_mapping et des valeurs de coordonnées plutôt que dans des "
            "balises fixes; pas encore analysés en champs structurés SCR/"
            "BoundingBox.",
            "Lignée/provenance et champs de distribution au-delà des attributs "
            "globaux en texte libre « history » et « source ».",
        ],
    },
    "Remote Sensing (LiDAR)": {
        "standard_name": "ISO 19115 (Information géographique — Métadonnées) / ASPRS LAS",
        "secondary_label": "ASPRS — spécification LAS",
        "covered": [
            "Version LAS, format des données de points (ce que stocke chaque "
            "enregistrement de point — XYZ seulement, +temps GPS, +couleur RVB, "
            "+proche infrarouge), nombre de points, boîte englobante 3D (X/Y/Z "
            "min-max), logiciel générateur, date de création.",
            "Référence spatiale : SCR (code EPSG, WKT), lue dans la balise de "
            "projection de l'en-tête (clés GeoTIFF ou WKT de LAS 1.4), lorsqu'elle "
            "est présente.",
        ],
        "not_covered": [
            "Le SCR est souvent absent des en-têtes LAS/LAZ, même dans des "
            "fichiers par ailleurs bien formés — c'est une pratique courante, pas "
            "forcément une erreur, mais le système de coordonnées doit alors être "
            "confirmé par la documentation du projet (p. ex. un README) plutôt que "
            "présumé. Signalé comme risque de curation NO_CRS_FOUND lorsqu'il "
            "manque.",
            "Le schéma de classification des points, les paramètres de vol/"
            "d'acquisition (capteur, hauteur de vol, angle de balayage) et la "
            "densité de points ne sont pas résumés — il faudrait lire tous les "
            "enregistrements de points, et pas seulement l'en-tête, ce qui sort de "
            "la conception de cette application (inspection rapide de l'en-tête).",
        ],
    },
    "Astrophysical Simulation": {
        "standard_name": "IVOA Simulation Data Model (SimDM) — noyau descriptif seulement",
        "secondary_label": "Principes directeurs FAIR (Wilkinson et al., 2016)",
        "covered": [
            "Identité de l'exécution : code, étiquette, ID de l'exécution, numéro "
            "de sauvegarde, temps simulé.",
            "Configuration numérique lue dans la sortie : grille hydrodynamique, "
            "rayons des frontières, nombre de fluides, interrupteurs de chauffage "
            "et de combustion, disposition MPI.",
            "Intégration temporelle : pas de temps, nombre de Courant, historique "
            "de l'exécution avec détection des redémarrages, nombre de Mach "
            "maximal.",
            "Organisation des données des cubes 3D bruts (géométrie des sous-cubes, "
            "complétude) et, lorsqu'un variables.json est présent, noms et unités "
            "des variables.",
            "Stratification initiale (fichier de configuration) : modèle stellaire, "
            "plage radiale, constantes de l'état de base.",
        ],
        "not_covered": [
            "Auteurs, licence, DOI, financement et citation : ils figurent dans le "
            "README/release.json du jeu de données, pas dans les fichiers de "
            "simulation, et doivent être fournis lors du dépôt.",
            "Version du code et options physiques au-delà des indicateurs fournis "
            "avec une diffusion de données (PPMstar est propriétaire; sa "
            "configuration complète n'est pas divulguée).",
            "Valeurs des données des cubes (plages, masques NaN, moyennes "
            "sphériques) : la taille des cubes est mesurée, mais ils ne sont "
            "jamais lus — ils atteignent 2,3 Go par fichier.",
            "Noms et unités des variables des cubes lorsqu'aucun variables.json ne "
            "se trouve à moins de quatre dossiers du cube : les blocs float32 bruts "
            "n'ont pas d'en-tête.",
            "Sommes de contrôle de fichiers entiers : utilisez l'action Intégrité "
            "> Vérifier le manifeste avec le MANIFEST.sha256 du jeu de données.",
        ],
    },
    "Astronomy": {
        "standard_name": "FITS (Flexible Image Transport System)",
        "secondary_label": "Documentation de astropy.io.fits",
        "covered": [
            "Cartes d'en-tête : télescope, instrument, objet, date d'observation "
            "(DATE-OBS, MJD-OBS, DATE-END), temps d'exposition, filtre, "
            "dimensions, auteur/origine/créateur, observateur, ID de la "
            "proposition, système de temps, BUNIT, BSCALE/BZERO.",
            "WCS (World Coordinate System) : valeur et pixel de référence, échelle "
            "des pixels, matrice CD ou PC, unités des axes, angles du pôle, type "
            "de coordonnée, référentiel, équinoxe; ainsi qu'une vérification que "
            "astropy peut construire un WCS céleste et l'échelle de pixel "
            "obtenue en arcsec/pixel.",
            "Inventaire des HDU : type de chaque HDU (image, table binaire/ASCII, "
            "image compressée), nom, forme et dtype de l'image, ou nombre de "
            "lignes et de colonnes de la table avec noms et unités des colonnes.",
            "Images stockées dans une extension (FITS multi-extensions ou "
            "compressé) : dimensions, BITPIX, WCS et clés d'en-tête manquantes "
            "sont lus dans la première extension d'image 2D lorsque le HDU "
            "principal est vide.",
            "Nombre de cartes HISTORY et COMMENT.",
        ],
        "not_covered": [
            "Clés d'en-tête des extensions autres que le premier HDU d'image 2D "
            "(p. ex. WCS par détecteur dans une mosaïque à plusieurs extensions "
            "d'image).",
            "Valeurs des pixels et contenu des tables : seuls les en-têtes sont "
            "lus; les statistiques d'image, la saturation et les données des "
            "lignes de tables ne sont donc pas résumées.",
            "Le texte des cartes HISTORY/COMMENT et les mots-clés propres à un "
            "instrument (p. ex. conventions HST, JWST, Gemini) au-delà de "
            "l'ensemble commun.",
            "Axes WCS non célestes (spectral, temps) et termes de distorsion "
            "(SIP, TPV) au-delà de la vérification de validité.",
        ],
    },
}
