# i18n/strings_fr.py
#
# French UI strings. Keys must match strings_en.py exactly — tests assert
# key parity so the language selector never falls back to English mid-UI.

STRINGS_FR = {
    # --- Window / top bar ---
    "window_title": "Visionneuse de métadonnées d'image",
    "label_select_format": "Sélectionner le format :",
    "label_select_application": "Sélectionner l'application :",
    "btn_standards_info": "Info sur la norme de métadonnées",
    "label_select_file": "Sélectionner le fichier :",
    "label_language": "Langue :",

    # --- Sidebar: File ---
    "group_file": "Fichier",
    "btn_load_file": "Charger un fichier",
    "btn_load_folder": "Charger un dossier",

    # --- Sidebar: Export ---
    "group_export": "Exporter",
    "btn_export_json": "Exporter en JSON",
    "btn_export_csv": "Exporter en CSV",
    "btn_export_curation": "Exporter le rapport de curation",
    "btn_batch_compliance": "Résumé de conformité du lot",
    "tooltip_batch_compliance": "Agrège le nombre de champs manquants et d'indicateurs de curation pour tous les fichiers chargés — ce jeu de données est-il prêt dans l'ensemble ?",

    # --- Sidebar: Write-back ---
    "group_write": "Écriture",
    "btn_write_metadata": "Écrire les métadonnées dans le fichier",
    "btn_save_sidecar": "Enregistrer le fichier JSON associé",
    "tooltip_save_sidecar": "Enregistre les métadonnées dans un fichier .json à côté de l'image (même dossier, même nom de base).",

    # --- Sidebar: Integrity ---
    "group_integrity": "Intégrité",
    "btn_save_checksums": "Enregistrer les sommes de contrôle",
    "tooltip_save_checksums": "Écrit checksums.json pour le dossier des fichiers chargés, pour de futures vérifications d'intégrité.",
    "btn_verify_integrity": "Vérifier l'intégrité",
    "tooltip_verify_integrity": "Compare les sommes de contrôle actuelles à un fichier checksums.json enregistré.",

    # --- Sidebar: View ---
    "group_view": "Affichage",
    "btn_hide_preview": "Masquer l'aperçu",
    "btn_show_preview": "Afficher l'aperçu",
    "label_no_preview": "Aucun aperçu",

    # --- Tabs ---
    "tab_raw_metadata": "Métadonnées brutes",
    "tab_recommended_fields": "Champs recommandés",
    "tab_curation": "Curation",
    "placeholder_raw_metadata": "Les métadonnées brutes s'afficheront ici",
    "placeholder_recommended_fields": "Les champs standardisés/recommandés s'afficheront ici",
    "placeholder_curation": "Les indicateurs de curation et l'intégrité s'afficheront ici",

    # --- Standards info dialog ---
    "dialog_title_metadata_standard": "Norme de métadonnées — {context}",
    "text_no_standards_doc": "Aucune documentation de norme n'est encore enregistrée pour « {context} ».",
    "text_covers": "Ce que l'application extrait pour cette norme :",
    "text_not_covered": "Non couvert par les métadonnées du fichier (doit être fourni séparément) :",
    "btn_close": "Fermer",

    # --- File / folder dialogs ---
    "dialog_select_file": "Sélectionner un fichier",
    "dialog_select_folder": "Sélectionner un dossier",
    "msg_no_files_found_title": "Aucun fichier trouvé",
    "msg_no_files_found_text": "Aucun fichier image pris en charge n'a été trouvé dans ce dossier.",

    # --- Batch loading progress ---
    "progress_loading_files": "Chargement des fichiers...",
    "progress_cancel": "Annuler",
    "progress_batch_loading_title": "Chargement par lot",
    "progress_processing": "Traitement de {filename} ({current}/{total})",

    # --- Metadata editor dialog ---
    "dialog_title_edit_metadata": "Modifier les métadonnées avant l'écriture",
    "text_edit_metadata_note": (
        "Modifiez les valeurs ci-dessous, puis cliquez sur Enregistrer pour les écrire "
        "dans le fichier. Les champs à valeurs multiples (affichés en grisé) sont "
        "structurés et ne sont pas modifiables ici."
    ),

    # --- Write metadata ---
    "dialog_title_write_metadata": "Écrire les métadonnées dans le fichier",
    "confirm_overwrite_metadata": "Ceci écrasera les métadonnées de :\n{path}\n\nCette action est irréversible. Continuer ?",
    "msg_write_metadata_success": "Métadonnées écrites avec succès dans le fichier.",
    "msg_write_metadata_failed": "Échec de l'écriture des métadonnées : {error}",
    "tooltip_write_metadata_unsafe": (
        "L'écriture est désactivée pour ce format : elle écraserait des "
        "métadonnées structurelles (structure des canaux/plans OME-XML, ou "
        "géoréférencement GeoTIFF) qui ne peuvent pas être reconstruites à "
        "partir des données de pixels."
    ),
    "msg_write_unsafe_format": (
        "L'écriture des métadonnées est désactivée pour ce format car elle "
        "écraserait des métadonnées structurelles (OME-XML ou "
        "géoréférencement GeoTIFF) irrécupérables par la suite."
    ),

    # --- Curation report export ---
    "dialog_save_curation_report": "Enregistrer le rapport de curation",
    "msg_curation_report_success": "Rapport de curation enregistré avec succès.",
    "msg_curation_report_failed": "Échec de l'enregistrement du rapport de curation : {error}",

    # --- Integrity ---
    "msg_checksums_success": "Sommes de contrôle enregistrées pour {count} fichier(s) :\n{path}",
    "msg_checksums_failed": "Échec de l'enregistrement des sommes de contrôle : {error}",
    "msg_no_checksums_title": "Aucune somme de contrôle trouvée",
    "msg_no_checksums_text": "Aucun fichier checksums.json trouvé dans ce dossier.\nUtilisez d'abord « Enregistrer les sommes de contrôle » pour créer une référence.",
    "dialog_title_integrity_result": "Résultat de la vérification d'intégrité",

    # --- Sidecar ---
    "dialog_title_save_sidecar": "Enregistrer le fichier JSON associé",
    "confirm_overwrite_sidecar": "Un fichier associé existe déjà :\n{path}\n\nL'écraser ?",
    "msg_sidecar_success": "Fichier associé enregistré :\n{path}",
    "msg_sidecar_failed": "Échec de l'enregistrement du fichier associé : {error}",

    # --- JSON / CSV export ---
    "dialog_save_json": "Enregistrer en JSON",
    "msg_json_success": "Fichier JSON enregistré avec succès.",
    "msg_json_failed": "Échec de l'enregistrement du fichier JSON : {error}",
    "dialog_save_csv": "Enregistrer en CSV",
    "msg_csv_success": "Fichier CSV enregistré avec succès.",
    "msg_csv_failed": "Échec de l'enregistrement du fichier CSV : {error}",

    # --- Sidebar: LiDAR ---
    "group_lidar": "LiDAR",
    "btn_analyze_las": "Analyser la classification des points",
    "tooltip_analyze_las": "Lit les enregistrements de points complets (pas seulement l'en-tête) pour indiquer la répartition des classifications, la plage d'angle de balayage, la plage de temps GPS et le nombre de lignes de vol. Plus lent que le chargement normal — LAS/LAZ uniquement.",

    # --- LAS point-data analysis dialog ---
    "dialog_title_las_analysis": "Analyse des points LAS/LAZ",
    "las_analysis_header": "Analyse des points — {filename}",
    "las_classification_header": "Répartition de la classification des points :",
    "las_scan_angle_range": "Plage d'angle de balayage : {min:.1f}° à {max:.1f}°",
    "las_gps_time_range": "Plage de temps GPS : {min:.3f} à {max:.3f} ({type})",
    "las_gps_time_unavailable": "Temps GPS : non stocké par ce format de point.",
    "las_flight_line_count": "Lignes de vol (identifiants de source de point distincts) : {count}",
    "las_sensor_note": (
        "Remarque : le modèle du capteur et l'altitude de vol ne sont "
        "stockés nulle part dans un fichier LAS/LAZ (ni l'en-tête ni les "
        "points) — ces informations se trouvent dans la documentation "
        "externe du vol/de la mission, pas dans le nuage de points lui-même."
    ),

    # --- Batch compliance summary dialog ---
    "dialog_title_batch_compliance": "Résumé de conformité du lot",
    "compliance_summary_header": "{compliant} / {total} fichiers entièrement conformes (aucun champ requis manquant, aucun indicateur de curation)",
    "compliance_missing_fields_header": "Champs requis manquants, par fréquence :",
    "compliance_curation_flags_header": "Indicateurs de curation, par fréquence :",
    "compliance_files_count": "{count} fichier(s)",
    "compliance_all_clear": "Tous les fichiers sont entièrement conformes — aucun champ requis manquant ni indicateur de curation.",

    # --- Generic dialog titles ---
    "msg_success_title": "Succès",
    "msg_error_title": "Erreur",

    # --- Metadata display content ---
    "label_file": "Fichier :",
    "text_metadata_extraction_failed": "L'extraction des métadonnées a échoué.",
    "text_error_prefix": "Erreur : {error}",

    # --- Recommended Fields tab: missing required fields ---
    "missing_fields_label": "Champs requis manquants :",

    # --- Curation tab rendering ---
    "curation_summary_title": "Résumé de curation — {filename}",
    "curation_flags_label": "Indicateurs :",
    "curation_ok_text": "OK — aucun problème détecté",
    "curation_md5_label": "Somme de contrôle MD5 :",
    "curation_compression_warning_label": "Avertissement de compression :",
    "curation_standard_label": "Norme de métadonnées :",
    "curation_reference_label": "Référence :",
}
