'''
Custom Optolink-Splitter profile for Daniel's VScotHO1 / device 20CB.
Generated from the supplied vcontrold.xml, vito.xml and Home Assistant MQTT YAML.
profile-id: vscotho1-20cb-ha-compat-v1
'''

poll_interval = 10

poll_groups = {
    "FAST": 1,
    "NORMAL": 3,
    "SLOW": 30,
    "RARE": 180,
}

poll_items = [
    ('NORMAL', 'heizkreis_m1_betriebsart', 0x2323, 1, 1, False),  # legacy=getBetriebArtM1; Betriebsart M1
    ('RARE', 'brenner_starts', 0x088A, 4, 1, True),  # legacy=getBrennerStarts; Ermittle die Brennerstarts
    ('FAST', 'brenner_modulation', 0x55D3, 1, 1, False),  # legacy=getBrennerStatus; Ermittle den Brennerstatus
    ('RARE', 'brenner_betriebsstunden_1', 0x08A7, 4, 0.0002777777777777778, False),  # legacy=getBrennerStunden1; Ermittle die Brennerstunden Stufe 1
    ('RARE', 'brenner_betriebsstunden_2', 0x08AB, 4, 0.0002777777777777778, False),  # legacy=getBrennerStunden2; Ermittle die Brennerstunden Stufe 2
    ('NORMAL', 'heizkreis_m1_pumpe_reduziert_drehzahl', 0x27E9, 1, 1, False),  # legacy=getDrehzahlReduziertA1M1; (E9) Reduzierte Drehzahl geregelte Pumpe A1M1
    ('NORMAL', 'externe_anforderung_pumpeneinfluss', 0x5734, 1, 1, True),  # legacy=getEinflussExtAnforderung; Einfluss Externe Anforderung auf Pumpen
    ('NORMAL', 'externe_sperre_pumpeneinfluss', 0x5732, 1, 1, True),  # legacy=getEinflussExtSperren; Einfluss Extern Sperren auf Pumpen
    ('RARE', 'fehlerhistorie_1', 0x7507, 9, 'b:0:0', 'f:02X', False),  # legacy=getError0; Ermittle Fehlerhistory Eintrag 1
    ('RARE', 'fehlerhistorie_2', 0x7510, 9, 'b:0:0', 'f:02X', False),  # legacy=getError1; Ermittle Fehlerhistory Eintrag 2
    ('RARE', 'fehlerhistorie_3', 0x7519, 9, 'b:0:0', 'f:02X', False),  # legacy=getError2; Ermittle Fehlerhistory Eintrag 3
    ('RARE', 'fehlerhistorie_4', 0x7522, 9, 'b:0:0', 'f:02X', False),  # legacy=getError3; Ermittle Fehlerhistory Eintrag 4
    ('RARE', 'fehlerhistorie_5', 0x752B, 9, 'b:0:0', 'f:02X', False),  # legacy=getError4; Ermittle Fehlerhistory Eintrag 5
    ('RARE', 'fehlerhistorie_6', 0x7534, 9, 'b:0:0', 'f:02X', False),  # legacy=getError5; Ermittle Fehlerhistory Eintrag 6
    ('RARE', 'fehlerhistorie_7', 0x753D, 9, 'b:0:0', 'f:02X', False),  # legacy=getError6; Ermittle Fehlerhistory Eintrag 7
    ('RARE', 'fehlerhistorie_8', 0x7546, 9, 'b:0:0', 'f:02X', False),  # legacy=getError7; Ermittle Fehlerhistory Eintrag 8
    ('RARE', 'fehlerhistorie_9', 0x754F, 9, 'b:0:0', 'f:02X', False),  # legacy=getError8; Ermittle Fehlerhistory Eintrag 9
    ('RARE', 'fehlerhistorie_10', 0x7558, 9, 'b:0:0', 'f:02X', False),  # legacy=getError9; Ermittle Fehlerhistory Eintrag 10
    ('NORMAL', 'externe_anforderung_aktiv', 0x0A80, 1, 1, False),  # legacy=getExtAnforderung; Ist Externe Anforderung aktiv
    ('NORMAL', 'externe_sperre_aktiv', 0x0A81, 1, 1, False),  # legacy=getExtSperren; Ist Extern Sperren aktiv
    ('NORMAL', 'heizkreis_m1_frostgrenze_a3', 0x27A3, 1, 1, False),  # legacy=getKA3_KonfiFrostgrenzeM1_GWG; Ermittle die eingestellte Frostgrenze A1M1
    ('NORMAL', 'heizkreis_m1_pumpenlogik_a5', 0x27A5, 1, 1, False),  # legacy=getKA5; Ermittle die Heizkreispumpenlogik-Funktion
    ('NORMAL', 'heizkreis_m1_sommersparabschaltung_a6', 0x27A6, 1, 1, False),  # legacy=getKA6; Ermittle die AbsolutSommersparschaltung
    ('NORMAL', 'mischer_m2_einfluss_interne_pumpe', 0x37A8, 1, 1, True),  # legacy=getKonfiWirkung_aufPumpe; Ermittle Einfluss Mischer auf int UWP
    ('FAST', 'anlagenleistung', 0xA38F, 2, 'b:0:0', 0.5, False),  # legacy=getLeistungIst; Ermittle Anlagen Ist-Leistung
    ('NORMAL', 'heizkreis_m1_pumpe_max_drehzahl', 0x27E6, 1, 1, False),  # legacy=getMaxDrehzahlA1M1
    ('NORMAL', 'heizkreis_m1_pumpe_min_drehzahl', 0x27E7, 1, 1, False),  # legacy=getMinDrehzahlA1M1
    ('NORMAL', 'heizkreis_m1_heizkennlinie_neigung', 0x27D3, 1, 0.1, True),  # legacy=getNeigungM1
    ('NORMAL', 'heizkreis_m1_heizkennlinie_niveau', 0x27D4, 1, 1, True),  # legacy=getNiveauM1
    ('FAST', 'interne_pumpe_drehzahl', 0x7660, 2, 'b:1:1', 1, False),  # legacy=getPumpeDrehzahlIntern
    ('FAST', 'interne_pumpe_status', 0x7660, 1, 1, False),  # legacy=getPumpeStatusIntern
    ('FAST', 'heizkreis_m1_pumpe_drehzahl', 0x7663, 2, 'b:1:1', 1, False),  # legacy=getPumpeStatusM1
    ('FAST', 'zirkulationspumpe_status', 0x6515, 1, 1, False),  # legacy=getPumpeStatusZirku
    ('NORMAL', 'heizkreis_m1_pumpe_nebenbetrieb_drehzahl', 0x27E8, 1, 1, False),  # legacy=getSollDrehzahlNebenbetriebA1M1
    ('NORMAL', 'heizkreis_m1_frostschutz_status', 0x2500, 1, 1, True),  # legacy=getStatusFrostM1
    ('FAST', 'sammelstoerung', 0x0A82, 1, 1, False),  # legacy=getStatusStoerung
    ('RARE', 'systemzeit', 0x088E, 8, 'vdatetime', False),  # legacy=getSystemTime
    ('FAST', 'aussentemperatur', 0x0800, 2, 0.1, True),  # legacy=getTempA
    ('NORMAL', 'abgastemperatur', 0x0808, 2, 0.1, True),  # legacy=getTempAbgas
    ('NORMAL', 'aussentemperatur_gedaempft', 0x5527, 2, 0.1, True),  # legacy=getTempAged
    ('NORMAL', 'kessel_offset_ueber_warmwasser_soll', 0x6760, 1, 1, False),  # legacy=getTempKOffset
    ('FAST', 'kessel_isttemperatur', 0x0802, 2, 0.1, True),  # legacy=getTempKist
    ('NORMAL', 'kessel_solltemperatur', 0x555A, 2, 0.1, True),  # legacy=getTempKsoll
    ('NORMAL', 'legacy_max_vorlauftemperatur_m1', 0x2306, 1, 0.1, True),  # legacy=getTempMaxVorlauf; source conflict with room setpoint
    ('NORMAL', 'heizkreis_m1_party_solltemperatur', 0x2308, 1, 1, True),  # legacy=getTempPartyM1
    ('NORMAL', 'legacy_ruecklauftemperatur_17a', 0x0808, 2, 0.1, True),  # legacy=getTempRL17A; source conflict with exhaust temperature
    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_normal', 0x2306, 1, 1, False),  # legacy=getTempRaumNorSollM1
    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_reduziert', 0x2307, 1, 1, False),  # legacy=getTempRaumRedSollM1
    ('FAST', 'heizkreis_m1_vorlauftemperatur', 0x2900, 2, 0.1, True),  # legacy=getTempVListM1
    ('FAST', 'heizkreis_m1_vorlaufsolltemperatur', 0x2544, 2, 0.1, True),  # legacy=getTempVLsollM1
    ('FAST', 'warmwasser_isttemperatur', 0x0804, 2, 0.1, True),  # legacy=getTempWWist
    ('NORMAL', 'warmwasser_solltemperatur', 0x6300, 1, 1, False),  # legacy=getTempWWsoll
    ('RARE', 'heizkreis_m1_zeitprogramm_dienstag', 0x2008, 8, 'schedvdens', False),  # legacy=getTimerM1Di
    ('RARE', 'heizkreis_m1_zeitprogramm_donnerstag', 0x2018, 8, 'schedvdens', False),  # legacy=getTimerM1Do
    ('RARE', 'heizkreis_m1_zeitprogramm_freitag', 0x2020, 8, 'schedvdens', False),  # legacy=getTimerM1Fr
    ('RARE', 'heizkreis_m1_zeitprogramm_mittwoch', 0x2010, 8, 'schedvdens', False),  # legacy=getTimerM1Mi
    ('RARE', 'heizkreis_m1_zeitprogramm_montag', 0x2000, 8, 'schedvdens', False),  # legacy=getTimerM1Mo
    ('RARE', 'heizkreis_m1_zeitprogramm_samstag', 0x2028, 8, 'schedvdens', False),  # legacy=getTimerM1Sa
    ('RARE', 'heizkreis_m1_zeitprogramm_sonntag', 0x2030, 8, 'schedvdens', False),  # legacy=getTimerM1So
    ('FAST', 'umschaltventil_stellung', 0x0A10, 1, 1, False),  # legacy=getUmschaltventil
]
