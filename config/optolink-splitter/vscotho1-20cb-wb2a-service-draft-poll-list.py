'''
DRAFT ONLY - NOT ACTIVE / NOT REFERENCED BY THE INSTALLER

Service-manual-oriented poll profile for:
  Viessmann Vitodens 200, type WB2A
  controller/device: VScotHO1 / 20CB, P300

Purpose:
  Build a clean successor to the legacy-vcontrold-compatible profile before
  Home Assistant is migrated to native MQTT discovery.

Source priority:
  1. Viessmann WB2A service manual 5681 573 (10/2006) defines which values,
     operating states and coding addresses belong to this appliance.
  2. The currently working local VScotHO1/20CB mapping and openv/vcontrold
     xml/300/vito.xml provide raw Optolink addresses.
  3. SmartHomeNG's Viessmann command map is used to cross-check A1/M1 and M2
     coding-address translations such as A3 -> 0x27A3 and C6 -> 0x27C6.

Important:
  The service manual itself does NOT document raw Optolink/P300 addresses.
  Therefore values without a sufficiently cross-checked raw address are not
  invented here; they are listed as TODOs at the bottom instead.

profile-id: vscotho1-20cb-wb2a-service-draft-v1
'''

# Keep the fast runtime values responsive while leaving configuration and
# counters at conservative intervals.
poll_interval = 2

poll_groups = {
    "ONCE": 0,              # startup / forcepoll only
    "FAST": 1,              # about 2 s
    "NORMAL": 15,           # about 30 s
    "SLOW": 150,            # about 5 min
    "RARE": 900,            # about 30 min

    # Hardware-dependent blocks stay disabled until the real installation
    # topology has been audited.
    "OPTIONAL_M2": -1,
    "OPTIONAL_SOLAR": -1,
    "OPTIONAL_COMBI": -1,

    # Known addresses that are useful for diagnostics but are not part of the
    # WB2A service display or still need appliance-specific validation.
    "EXPERIMENTAL": -1,

    # Vitosoft-derived points found specifically in the VScotHO1_20 catalog.
    # Keep disabled until 0x00F8/0x00F0 identifies the real controller variant.
    "CANDIDATE_VSCOTHO1_20": -1,
}


poll_items = [
    # -------------------------------------------------------------------------
    # Identity / installation
    # -------------------------------------------------------------------------
    # Full 8-byte identifier is needed because 20CB alone does not identify
    # the VScotHO1 software/datapoint variant. F0 further splits later variants.
    ('ONCE', 'device_ident_raw', 0x00F8, 8),
    ('ONCE', 'device_ident_f0_raw', 0x00F0, 1),
    ('ONCE', 'anlagenschema', 0x7700, 2, 'b:0:0', 1, False),
    ('ONCE', 'sachnummer_raw', 0x08E0, 7),
    ('ONCE', 'codierstecker_sachnummer_raw', 0x1010, 7),
    ('ONCE', 'bedienteil_sw_index_raw', 0x7330, 8),

    # -------------------------------------------------------------------------
    # Core temperatures / combustion / hydraulic state
    # Service manual: temperatures and operating states, pp. 60 and 65.
    # -------------------------------------------------------------------------
    ('FAST', 'aussentemperatur', 0x0800, 2, 0.1, True),
    ('NORMAL', 'aussentemperatur_tiefpass', 0x5525, 2, 0.1, True),
    ('NORMAL', 'aussentemperatur_gedaempft', 0x5527, 2, 0.1, True),

    ('FAST', 'kessel_isttemperatur', 0x0802, 2, 0.1, True),
    ('FAST', 'kessel_solltemperatur', 0x555A, 2, 0.1, True),
    ('NORMAL', 'abgastemperatur', 0x0808, 2, 0.1, True),

    ('FAST', 'warmwasser_isttemperatur', 0x0804, 2, 0.1, True),
    ('NORMAL', 'warmwasser_solltemperatur', 0x6300, 1, 1, False),

    ('FAST', 'brenner_modulation', 0x55D3, 1, 1, False),
    ('FAST', 'anlagenleistung', 0xA38F, 2, 'b:0:0', 0.5, False),

    # 20CB-specific pump mappings. One 2-byte read of 0x7660 feeds status and
    # speed by adjacent-byte filters.
    ('FAST', 'interne_pumpe_status', 0x7660, 2, 'b:0:0', 1, False),
    ('FAST', 'interne_pumpe_drehzahl', 0x7660, 2, 'b:1:1', 1, False),
    ('FAST', 'heizkreis_m1_pumpe_drehzahl', 0x7663, 2, 'b:1:1', 1, False),

    # 20CB overrides from openv/vcontrold.
    ('FAST', 'speicherladepumpe_status', 0x6513, 1, 1, False),
    ('FAST', 'zirkulationspumpe_status', 0x6515, 1, 1, False),
    ('FAST', 'umschaltventil_stellung', 0x0A10, 1, 1, False),
    ('FAST', 'sammelstoerung', 0x0A82, 1, 1, False),

    ('NORMAL', 'externe_anforderung_aktiv', 0x0A80, 1, 1, False),
    ('NORMAL', 'externe_sperre_aktiv', 0x0A81, 1, 1, False),
    ('SLOW', 'externe_anforderung_pumpeneinfluss', 0x5734, 1, 1, True),
    ('SLOW', 'externe_sperre_pumpeneinfluss', 0x5732, 1, 1, True),

    # -------------------------------------------------------------------------
    # Heating circuit A1/M1 - runtime and setpoints
    # -------------------------------------------------------------------------
    ('NORMAL', 'heizkreis_m1_betriebsart', 0x2323, 1, 1, False),
    # Vitosoft/openv expose these as the live states for economy/party mode.
    # Keep them as observations for now; write semantics are documented below.
    ('NORMAL', 'heizkreis_m1_sparbetrieb', 0x2302, 1, 1, False),
    ('NORMAL', 'heizkreis_m1_partybetrieb', 0x2303, 1, 1, False),
    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_normal', 0x2306, 1, 1, False),
    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_reduziert', 0x2307, 1, 1, False),
    ('NORMAL', 'heizkreis_m1_party_solltemperatur', 0x2308, 1, 1, True),

    ('FAST', 'heizkreis_m1_vorlauftemperatur', 0x2900, 2, 0.1, True),
    ('FAST', 'heizkreis_m1_vorlaufsolltemperatur', 0x2544, 2, 0.1, True),
    ('NORMAL', 'heizkreis_m1_frostschutz_status', 0x2500, 1, 1, True),

    # -------------------------------------------------------------------------
    # Heating circuit A1/M1 - WB2A service coding
    #
    # The old migration profile contained a legacy source conflict that mapped
    # "max supply temperature" to 0x2306. The WB2A manual identifies the
    # maximum supply-temperature limit as coding C6, and the cross-checked raw
    # A1/M1 address is 0x27C6. This draft uses the corrected mapping.
    # -------------------------------------------------------------------------
    ('SLOW', 'heizkreis_m1_speichervorrang_a2', 0x27A2, 1, 1, False),
    ('SLOW', 'heizkreis_m1_frostgrenze_a3', 0x27A3, 1, 1, True),
    ('SLOW', 'heizkreis_m1_frostschutz_a4', 0x27A4, 1, 1, False),
    ('SLOW', 'heizkreis_m1_pumpenlogik_a5', 0x27A5, 1, 1, True),
    ('SLOW', 'heizkreis_m1_sommersparabschaltung_a6', 0x27A6, 1, 1, False),
    ('SLOW', 'heizkreis_m1_mischersparfunktion_a7', 0x27A7, 1, 1, False),
    ('SLOW', 'heizkreis_m1_pumpenstillstandzeit_a9', 0x27A9, 1, 1, False),

    ('SLOW', 'heizkreis_m1_vorlauf_min_c5', 0x27C5, 1, 1, False),
    ('SLOW', 'heizkreis_m1_vorlauf_max_c6', 0x27C6, 1, 1, False),

    ('SLOW', 'heizkreis_m1_heizkennlinie_neigung_d3', 0x27D3, 1, 0.1, False),
    ('SLOW', 'heizkreis_m1_heizkennlinie_niveau_d4', 0x27D4, 1, 1, True),

    ('SLOW', 'heizkreis_m1_pumpe_max_drehzahl_e6', 0x27E6, 1, 1, False),
    ('SLOW', 'heizkreis_m1_pumpe_min_drehzahl_e7', 0x27E7, 1, 1, False),
    ('SLOW', 'heizkreis_m1_pumpe_reduziert_regelart_e8', 0x27E8, 1, 1, False),
    ('SLOW', 'heizkreis_m1_pumpe_reduziert_drehzahl_e9', 0x27E9, 1, 1, False),

    ('SLOW', 'heizkreis_m1_party_zeitbegrenzung_f2', 0x27F2, 1, 1, False),

    ('SLOW', 'kessel_offset_ueber_warmwasser_soll', 0x6760, 1, 1, False),
    ('SLOW', 'warmwasser_pumpennachlauf', 0x6762, 2, 1, False),

    # -------------------------------------------------------------------------
    # Counters / time / fault history
    # Service manual exposes burner hours, starts, time/date and the last
    # 10 stored faults.
    # -------------------------------------------------------------------------
    ('RARE', 'brenner_starts', 0x088A, 4, 1, True),
    ('RARE', 'brenner_betriebsstunden_1', 0x08A7, 4, 0.0002777777777777778, False),
    ('RARE', 'brenner_betriebsstunden_2', 0x08AB, 4, 0.0002777777777777778, False),
    ('EXPERIMENTAL', 'betriebszeit_standby', 0x08B8, 4, 0.0002777777777777778, False),
    ('RARE', 'systemzeit', 0x088E, 8, 'vdatetime', False),

    ('RARE', 'fehlerhistorie_01', 0x7507, 9, 'b:0:0', 'f:02X', False),
    ('RARE', 'fehlerhistorie_02', 0x7510, 9, 'b:0:0', 'f:02X', False),
    ('RARE', 'fehlerhistorie_03', 0x7519, 9, 'b:0:0', 'f:02X', False),
    ('RARE', 'fehlerhistorie_04', 0x7522, 9, 'b:0:0', 'f:02X', False),
    ('RARE', 'fehlerhistorie_05', 0x752B, 9, 'b:0:0', 'f:02X', False),
    ('RARE', 'fehlerhistorie_06', 0x7534, 9, 'b:0:0', 'f:02X', False),
    ('RARE', 'fehlerhistorie_07', 0x753D, 9, 'b:0:0', 'f:02X', False),
    ('RARE', 'fehlerhistorie_08', 0x7546, 9, 'b:0:0', 'f:02X', False),
    ('RARE', 'fehlerhistorie_09', 0x754F, 9, 'b:0:0', 'f:02X', False),
    ('RARE', 'fehlerhistorie_10', 0x7558, 9, 'b:0:0', 'f:02X', False),

    # -------------------------------------------------------------------------
    # Time programs - low frequency; useful later for native HA entities.
    # -------------------------------------------------------------------------
    ('RARE', 'heizkreis_m1_zeitprogramm_montag', 0x2000, 8, 'schedvdens', False),
    ('RARE', 'heizkreis_m1_zeitprogramm_dienstag', 0x2008, 8, 'schedvdens', False),
    ('RARE', 'heizkreis_m1_zeitprogramm_mittwoch', 0x2010, 8, 'schedvdens', False),
    ('RARE', 'heizkreis_m1_zeitprogramm_donnerstag', 0x2018, 8, 'schedvdens', False),
    ('RARE', 'heizkreis_m1_zeitprogramm_freitag', 0x2020, 8, 'schedvdens', False),
    ('RARE', 'heizkreis_m1_zeitprogramm_samstag', 0x2028, 8, 'schedvdens', False),
    ('RARE', 'heizkreis_m1_zeitprogramm_sonntag', 0x2030, 8, 'schedvdens', False),

    ('RARE', 'warmwasser_zeitprogramm_montag', 0x2100, 8, 'schedvdens', False),
    ('RARE', 'warmwasser_zeitprogramm_dienstag', 0x2108, 8, 'schedvdens', False),
    ('RARE', 'warmwasser_zeitprogramm_mittwoch', 0x2110, 8, 'schedvdens', False),
    ('RARE', 'warmwasser_zeitprogramm_donnerstag', 0x2118, 8, 'schedvdens', False),
    ('RARE', 'warmwasser_zeitprogramm_freitag', 0x2120, 8, 'schedvdens', False),
    ('RARE', 'warmwasser_zeitprogramm_samstag', 0x2128, 8, 'schedvdens', False),
    ('RARE', 'warmwasser_zeitprogramm_sonntag', 0x2130, 8, 'schedvdens', False),

    ('RARE', 'zirkulation_zeitprogramm_montag', 0x2200, 8, 'schedvdens', False),
    ('RARE', 'zirkulation_zeitprogramm_dienstag', 0x2208, 8, 'schedvdens', False),
    ('RARE', 'zirkulation_zeitprogramm_mittwoch', 0x2210, 8, 'schedvdens', False),
    ('RARE', 'zirkulation_zeitprogramm_donnerstag', 0x2218, 8, 'schedvdens', False),
    ('RARE', 'zirkulation_zeitprogramm_freitag', 0x2220, 8, 'schedvdens', False),
    ('RARE', 'zirkulation_zeitprogramm_samstag', 0x2228, 8, 'schedvdens', False),
    ('RARE', 'zirkulation_zeitprogramm_sonntag', 0x2230, 8, 'schedvdens', False),

    # -------------------------------------------------------------------------
    # Optional heating circuit M2 - disabled until the installed topology and
    # mixer extension have been confirmed.
    # -------------------------------------------------------------------------
    ('OPTIONAL_M2', 'heizkreis_m2_sparbetrieb', 0x3302, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_partybetrieb', 0x3303, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_vorlauftemperatur', 0x3900, 2, 0.1, True),
    ('OPTIONAL_M2', 'heizkreis_m2_vorlaufsolltemperatur', 0x3544, 2, 0.1, True),
    ('OPTIONAL_M2', 'heizkreis_m2_pumpe_status_raw', 0x3906, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_mischer_position_raw', 0x354C, 1, 1, False),

    ('OPTIONAL_M2', 'heizkreis_m2_speichervorrang_a2', 0x37A2, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_frostgrenze_a3', 0x37A3, 1, 1, True),
    ('OPTIONAL_M2', 'heizkreis_m2_frostschutz_a4', 0x37A4, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_pumpenlogik_a5', 0x37A5, 1, 1, True),
    ('OPTIONAL_M2', 'heizkreis_m2_sommersparabschaltung_a6', 0x37A6, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_mischersparfunktion_a7', 0x37A7, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_einfluss_interne_pumpe_a8', 0x37A8, 1, 1, True),
    ('OPTIONAL_M2', 'heizkreis_m2_pumpenstillstandzeit_a9', 0x37A9, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_vorlauf_min_c5', 0x37C5, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_vorlauf_max_c6', 0x37C6, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_heizkennlinie_neigung_d3', 0x37D3, 1, 0.1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_heizkennlinie_niveau_d4', 0x37D4, 1, 1, True),

    ('OPTIONAL_M2', 'heizkreis_m2_zeitprogramm_montag', 0x3000, 8, 'schedvdens', False),
    ('OPTIONAL_M2', 'heizkreis_m2_zeitprogramm_dienstag', 0x3008, 8, 'schedvdens', False),
    ('OPTIONAL_M2', 'heizkreis_m2_zeitprogramm_mittwoch', 0x3010, 8, 'schedvdens', False),
    ('OPTIONAL_M2', 'heizkreis_m2_zeitprogramm_donnerstag', 0x3018, 8, 'schedvdens', False),
    ('OPTIONAL_M2', 'heizkreis_m2_zeitprogramm_freitag', 0x3020, 8, 'schedvdens', False),
    ('OPTIONAL_M2', 'heizkreis_m2_zeitprogramm_samstag', 0x3028, 8, 'schedvdens', False),
    ('OPTIONAL_M2', 'heizkreis_m2_zeitprogramm_sonntag', 0x3030, 8, 'schedvdens', False),

    # -------------------------------------------------------------------------
    # Optional solar extension - disabled until Vitosolic / sensors are known.
    # The manual exposes these values only when the corresponding equipment is
    # installed.
    # -------------------------------------------------------------------------
    ('OPTIONAL_SOLAR', 'solar_kollektortemperatur', 0x6564, 2, 0.1, True),
    ('OPTIONAL_SOLAR', 'solar_warmwassertemperatur', 0x6566, 2, 0.1, True),
    ('OPTIONAL_SOLAR', 'solar_nachladeunterdrueckung_status', 0x6551, 1, 1, False),
    ('OPTIONAL_SOLAR', 'solarpumpe_status', 0x6552, 1, 1, False),
    ('OPTIONAL_SOLAR', 'solarpumpe_betriebsstunden', 0x6568, 2, 1, False),
    ('OPTIONAL_SOLAR', 'solarenergie_raw', 0x6560, 4, 1, False),
    ('OPTIONAL_SOLAR', 'solar_sensor_temperatur', 0x081A, 2, 0.1, True),

    # -------------------------------------------------------------------------
    # Optional combi-water-heater outlet sensor.
    # -------------------------------------------------------------------------
    ('OPTIONAL_COMBI', 'warmwasser_auslauftemperatur', 0x0814, 2, 0.1, True),

    # -------------------------------------------------------------------------
    # VScotHO1_20 candidates from a Vitosoft-derived datapoint catalogue.
    # These are deliberately disabled until the full F8/F0 identification says
    # the controller actually belongs to that software family.
    # -------------------------------------------------------------------------
    ('CANDIDATE_VSCOTHO1_20', 'kessel_maximaltemperatur_06', 0x5706, 1, 1, False),
    ('CANDIDATE_VSCOTHO1_20', 'kennung_interne_pumpe_30', 0x5730, 1, 1, False),
    ('CANDIDATE_VSCOTHO1_20', 'interne_pumpe_solldrehzahl_31', 0x5731, 1, 1, False),
    ('CANDIDATE_VSCOTHO1_20', 'heizkreis_m1_pumpentyp_e5', 0x27E5, 1, 1, False),

    ('CANDIDATE_VSCOTHO1_20', 'heizkreis_m1_estrichfunktion_f1', 0x27F1, 1, 1, False),
    ('CANDIDATE_VSCOTHO1_20', 'heizkreis_m1_reduziert_anhebung_start_f8', 0x27F8, 1, 1, True),
    ('CANDIDATE_VSCOTHO1_20', 'heizkreis_m1_reduziert_anhebung_ende_f9', 0x27F9, 1, 1, True),
    ('CANDIDATE_VSCOTHO1_20', 'heizkreis_m1_vorlauf_ueberhoehung_fa', 0x27FA, 1, 1, False),
    ('CANDIDATE_VSCOTHO1_20', 'heizkreis_m1_vorlauf_ueberhoehung_dauer_fb', 0x27FB, 1, 2, False),

    ('CANDIDATE_VSCOTHO1_20', 'zirkulation_bei_ww_soll1_71', 0x6771, 1, 1, False),
    ('CANDIDATE_VSCOTHO1_20', 'zirkulation_bei_ww_soll2_72', 0x6772, 1, 1, False),
    ('CANDIDATE_VSCOTHO1_20', 'zirkulation_intervall_73', 0x6773, 1, 1, False),
    ('CANDIDATE_VSCOTHO1_20', 'relais_k12_funktion_53', 0x7753, 1, 1, False),

    # VScotHO1_20 exposes flame/lockout flags in a larger block beginning at
    # 0x55D3. The active legacy profile intentionally still uses its verified
    # one-byte modulation read instead; these flags need hardware verification.
    ('CANDIDATE_VSCOTHO1_20', 'brenner_flamme_block_candidate', 0x55D3, 9, 'b:5:5:0x20', 'bool', False),
    ('CANDIDATE_VSCOTHO1_20', 'feuerungsautomat_verriegelt_candidate', 0x55D3, 9, 'b:5:5:0x40', 'bool', False),

    # -------------------------------------------------------------------------
    # Experimental diagnostics - useful raw datapoints but not yet promoted.
    # -------------------------------------------------------------------------
    ('EXPERIMENTAL', 'volumenstrom_raw', 0x0C24, 2, 1, False),
    ('EXPERIMENTAL', 'kesseltemperatur_tiefpass', 0x0810, 2, 0.1, True),

    # Community configurations use these as fan-speed setpoint/actual RPM.
    # They were NOT found as normal Virtual_READ points in the VScotHO1_20
    # Vitosoft-derived catalogue; test read-only before considering promotion.
    ('EXPERIMENTAL', 'geblaese_drehzahl_soll_candidate', 0x0B1C, 2, 1, False),
    ('EXPERIMENTAL', 'geblaese_drehzahl_ist_candidate', 0x0B1E, 2, 1, False),
]


# ---------------------------------------------------------------------------
# WB2A manual values still intentionally missing from poll_items
# ---------------------------------------------------------------------------
#
# The manual documents the following values/functions, but this draft does not
# assign a raw P300 address until it is verified for device 20CB:
#
# - actual room temperature
# - external room-temperature setpoint
# - common supply temperature actual/setpoint for hydraulic separator
# - internal-extension output state
# - mixer open/close relay state (position value above is not the same thing)
# - WW outlet setpoint for combi appliance
# - coding 1E: gas type
# - coding 2F: venting/filling program
# - coding 77: LON participant number
# - coding E5: variable-speed external pump detected/type
# - F5/F6/F7 heating-circuit functions (not present in the located
#   VScotHO1_20 standard Optolink catalogue)
#
# Control/write research notes:
# - Party state is readable at 0x2303 and economy state at 0x2302.
# - Some openv/community configurations write those same addresses.
# - Later Vitogate/Vitosoft-derived variants expose command targets 0x2330
#   (party) and 0x2331 (economy). Do not expose either write path until the
#   exact F8/F0 variant and hardware behaviour have been verified.
# - 0x6515 is a confirmed 20CB circulation-pump STATUS. The located VScotHO1_20
#   catalogue marks it as status; no equally strong source proves a direct
#   immediate ON/OFF write for this WB2A. Scheduling remains the safe control
#   path to investigate first.
# - VScotHO1_20 contains burner-controller process values P06/P09/P10 at
#   0x4006/0x4009/0x400A (fan actual/setpoint/PWM), but the generated standard
#   Optolink catalogue omits them, consistent with a non-Virtual_READ access
#   method. They are therefore not poll_items.
# - Community configs also use 0x0B1C/0x0B1E for fan setpoint/actual RPM on
#   other Optolink systems; they remain disabled EXPERIMENTAL candidates here.
# - A readable lockout state exists in VScotHO1_20 (block 0x55D3), but no
#   defensible WB2A Optolink command for burner fault unlocking/reset has been
#   located. Do not invent or automate such a write.
#
# Also note:
# - 0x0808 appears in historical sources both as exhaust temperature and as a
#   20CB override for a return-temperature command. Do not create two HA
#   entities from it until the real WB2A response semantics are verified.
# - The generic openv/vcontrold fault-status address 0x7579 is overridden for
#   device 20CB by 0x0A82, so this draft deliberately uses 0x0A82.
# - OPTIONAL_* groups are disabled by design and must not be enabled wholesale
#   until the connected WB2A hardware/options have been inventoried.
