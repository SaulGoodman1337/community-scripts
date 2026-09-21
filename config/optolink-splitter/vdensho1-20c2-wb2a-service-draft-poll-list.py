'''
DRAFT ONLY - NOT ACTIVE / NOT REFERENCED BY INSTALLER

Exact controller identification from the real appliance:
  0x00F8 read (8 bytes): 20 C2 00 03 00 00 01 03
  family: VDensHO1 / device 20C2
  software index: 0x03

This draft supersedes the earlier VScotHO1/20CB research draft for this WB2A.
It is intentionally kept separate from the active migration profile.

Primary sources:
  - Viessmann Vitodens 200 WB2A service manual
  - Vitosoft-derived VDensHO1 datapoint catalog
  - existing working legacy/vcontrold-compatible profile
  - OpenV/vcontrold data used only as a cross-check

No write-only or safety-relevant command is exposed here unless the VDensHO1
catalog clearly supports it and we have hardware-verified semantics.

Hardware verification on the real appliance (20C2 / software index 0x03):
  0x27C5 len1 -> 0x26
  0x27C6 len1 -> 0x32
  0x2302 len1 -> 0x00
  0x2303 len1 -> 0x00
  0x6515 len1 -> 0x01
  0x0842 len1 -> 0x01
  0x0810 len2 div10 signed -> 31.0 C
  0x0816 len2 div10 signed -> 31.6 C
  0x0896 len2 div10 signed -> 20.0 C
  0xA305 len1 *0.5 -> 0.0 %
  0x55D3 len9 -> 00 B2 B0 00 00 01 00 00 00
    byte 5 mask 0x20 -> flame false
    byte 5 mask 0x40 -> fire-control lockout false
  0x55DD len1 -> 0x01 (raw; mask 0x20 is false)
  0x0B1C len2 -> P300 error response (retcode 3, payload 0x01)
  0x0B1E len2 -> P300 error response (retcode 3, payload 0x01)
  0x2906 len1 -> 0x01 (A1/M1 heating-circuit pump ON)
  0x650A len1 -> 0x00 (DHW charging inactive)
  0x0A10 len1 -> 0x03 (diverter valve toward DHW)
  0x2500 len22 -> 02 01 00 00 00 00 00 00 01 00 00 01 B4 00 00 00 00 00 00 00 B4 00
    byte 1 -> 0x01 = reduced operation
    bytes 12..13 -> 0x00B4 = 18.0 C current effective room setpoint
    byte 16 bit 0 -> frost danger false
  0x2535 len1 -> 0x00 (holiday mode false)
  0x0883 len1 -> 0x00 (flow switch OFF)
  0x080C len2 div10 signed -> 20.0 C (readable; physical sensor presence still to verify)
  0x6500 len2 div10 signed -> 45.0 C current effective DHW setpoint
  Party mode enabled at the real control panel:
    0x2303 len1 -> 0x01 (party ON)
    0x2308 len1 -> 0x15 = 21 C party room setpoint
    0x2500 len22 -> 02 02 65 1A 00 00 00 00 02 00 00 01 D2 00 00 00 00 00 00 00 D2 00
      byte 1 -> 0x02 = normal operation while party mode is active
      bytes 12..13 -> 0x00D2 = 21.0 C effective room setpoint
      bytes 20..21 also mirror 0x00D2 in this sample
    0x0842 len1 -> 0x01 unchanged, so relay K12 does not track party mode
'''

poll_interval = 2

poll_groups = {
    "ONCE": 0,
    "FAST": 1,           # ~2 s
    "NORMAL": 15,        # ~30 s
    "SLOW": 150,         # ~5 min
    "RARE": 900,         # ~30 min

    # Optional hardware not yet inventoried on the real installation.
    "OPTIONAL_M2": -1,
    "OPTIONAL_SOLAR": -1,
    "OPTIONAL_EXT": -1,

    # Read-only candidates to verify manually before promotion.
    "EXPERIMENTAL": -1,
}

poll_items = [
    # ---------------------------------------------------------------------
    # Identification / topology
    # ---------------------------------------------------------------------
    ('ONCE', 'device_ident_raw', 0x00F8, 8),
    ('ONCE', 'anlagenschema', 0x7700, 2, 'b:0:0', 1, False),
    ('ONCE', 'codierstecker_sachnummer_raw', 0x1010, 7),
    ('ONCE', 'codierstecker_kennung_raw', 0x1040, 2),
    ('ONCE', 'bedienteil_sw_index', 0x7330, 1, 1, False),
    ('ONCE', 'gfa_kennung', 0x7650, 1, 1, False),

    # ---------------------------------------------------------------------
    # Core temperatures
    # VDensHO1 catalog uses the filtered sensor values for diagnosis.
    # ---------------------------------------------------------------------
    ('FAST', 'aussentemperatur', 0x0800, 2, 0.1, True),
    ('NORMAL', 'aussentemperatur_tiefpass', 0x5525, 2, 0.1, True),
    ('NORMAL', 'aussentemperatur_gedaempft', 0x5527, 2, 0.1, True),

    ('FAST', 'kesseltemperatur', 0x0810, 2, 0.1, True),  # HW verified: 31.0 C
    ('FAST', 'kessel_solltemperatur', 0x555A, 2, 0.1, True),
    ('NORMAL', 'abgastemperatur', 0x0816, 2, 0.1, True),  # HW verified: 31.6 C

    ('FAST', 'warmwasser_temperatur', 0x0812, 2, 0.1, True),
    ('NORMAL', 'warmwasser_solltemperatur', 0x6300, 1, 1, False),
    ('NORMAL', 'warmwasser_solltemperatur_aktuell', 0x6500, 2, 0.1, True),  # HW verified: 45.0 C

    ('OPTIONAL_EXT', 'hydraulische_weiche_temperatur', 0x080C, 2, 0.1, True),  # HW readable: 20.0 C; sensor presence TBD
    ('OPTIONAL_EXT', 'vorlaufsensor_vts_temperatur', 0x081A, 2, 0.1, True),

    # ---------------------------------------------------------------------
    # Burner / pumps / valves
    # ---------------------------------------------------------------------
    ('FAST', 'brenner_modulationsgrad', 0xA305, 1, 0.5, False),  # HW verified: 0.0 % while burner off

    # One two-byte read can feed both state and speed.
    ('FAST', 'interne_pumpe_status', 0x7660, 2, 'b:0:0', 1, False),
    ('FAST', 'interne_pumpe_drehzahl', 0x7660, 2, 'b:1:1', 1, False),

    ('FAST', 'heizkreis_m1_pumpe_drehzahl', 0x7663, 2, 'b:1:1', 1, False),
    ('FAST', 'heizkreis_m1_pumpe_status', 0x2906, 1, 1, False),  # HW verified: ON
    ('FAST', 'speicherladepumpe_status', 0x6513, 1, 1, False),
    ('FAST', 'warmwasser_ladestatus', 0x650A, 1, 1, False),  # HW verified: 0 = inactive
    ('FAST', 'zirkulationspumpe_status', 0x6515, 1, 1, False),  # HW verified: 1
    ('FAST', 'umschaltventil_stellung', 0x0A10, 1, 1, False),  # HW verified: 3 = Richtung Warmwasser
    ('FAST', 'relais_k12_status', 0x0842, 1, 1, False),  # HW verified: 1
    ('NORMAL', 'warmwasser_flowswitch', 0x0883, 1, 1, False),  # HW verified: OFF

    # The VDensHO1 catalog exposes flame and lockout as bit fields in the
    # 9-byte block beginning at 0x55D3.
    ('FAST', 'brenner_flamme', 0x55D3, 9, 'b:5:5:0x20', 'bool', False),  # HW verified block readable
    ('FAST', 'feuerungsautomat_verriegelt', 0x55D3, 9, 'b:5:5:0x40', 'bool', False),  # HW verified block readable

    # Alternative direct flame flag from the fire-control diagnostic block.
    ('NORMAL', 'brenner_flamme_gfa', 0x55DD, 1, 'b:0:0:0x20', 'bool', False),  # HW read raw=0x01, flame bit clear

    # ---------------------------------------------------------------------
    # Heating circuit A1/M1 - operating state
    # ---------------------------------------------------------------------
    ('NORMAL', 'heizkreis_m1_bedienteil_betriebsart', 0x2323, 1, 1, False),
    ('NORMAL', 'heizkreis_m1_sparbetrieb', 0x2302, 1, 1, False),  # HW verified: 0
    ('NORMAL', 'heizkreis_m1_partybetrieb', 0x2303, 1, 1, False),  # HW verified: 0=off, 1=on

    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_normal', 0x2306, 1, 1, False),
    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_reduziert', 0x2307, 1, 1, False),
    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_party', 0x2308, 1, 1, True),  # HW verified: raw 0x15 = 21 C

    ('NORMAL', 'heizkreis_m1_raumtemperatur', 0x0896, 2, 0.1, True),  # HW verified: 20.0 C

    # One 22-byte state block feeds multiple A1/M1 entities.
    # Hardware sample: 02 01 00 00 00 00 00 00 01 00 00 01 B4 00 00 00 00 00 00 00 B4 00
    ('NORMAL', 'heizkreis_m1_betriebsart_aktuell', 0x2500, 22, 'b:1:1', 1, False),  # HW verified: 1=Reduziert, 2=Normal during Party
    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_aktuell', 0x2500, 22, 'b:12:13', 0.1, True),  # HW verified: 18.0 C reduced, 21.0 C party
    ('NORMAL', 'heizkreis_m1_frostgefahr', 0x2500, 22, 'b:16:16:0x01', 'bool', False),  # HW verified: false
    ('NORMAL', 'heizkreis_m1_ferienbetrieb', 0x2535, 1, 'b:0:0:0x01', 'bool', False),  # HW verified: false

    ('FAST', 'heizkreis_m1_vorlaufsolltemperatur', 0x2544, 2, 0.1, True),

    # ---------------------------------------------------------------------
    # Heating circuit A1/M1 - service coding
    # ---------------------------------------------------------------------
    ('SLOW', 'heizkreis_m1_speichervorrang_a2', 0x27A2, 1, 1, False),
    ('SLOW', 'heizkreis_m1_frostgrenze_a3', 0x27A3, 1, 1, True),
    ('SLOW', 'heizkreis_m1_frostschutz_a4', 0x27A4, 1, 1, False),
    ('SLOW', 'heizkreis_m1_pumpenlogik_a5', 0x27A5, 1, 1, True),
    ('SLOW', 'heizkreis_m1_sommersparabschaltung_a6', 0x27A6, 1, 1, False),
    ('SLOW', 'heizkreis_m1_mischersparfunktion_a7', 0x27A7, 1, 1, False),
    ('SLOW', 'heizkreis_m1_pumpenstillstand_a9', 0x27A9, 1, 1, False),

    ('SLOW', 'heizkreis_m1_vorlauf_min_c5', 0x27C5, 1, 1, False),  # HW verified raw=0x26
    ('SLOW', 'heizkreis_m1_vorlauf_max_c6', 0x27C6, 1, 1, False),  # HW verified raw=0x32

    ('SLOW', 'heizkreis_m1_heizkennlinie_neigung_d3', 0x27D3, 1, 0.1, False),
    ('SLOW', 'heizkreis_m1_heizkennlinie_niveau_d4', 0x27D4, 1, 1, True),

    ('SLOW', 'heizkreis_m1_pumpentyp_e5', 0x27E5, 1, 1, False),
    ('SLOW', 'heizkreis_m1_pumpe_max_drehzahl_e6', 0x27E6, 1, 1, False),
    ('SLOW', 'heizkreis_m1_pumpe_min_drehzahl_e7', 0x27E7, 1, 1, False),
    ('SLOW', 'heizkreis_m1_pumpe_nebenbetrieb_e8', 0x27E8, 1, 1, False),
    ('SLOW', 'heizkreis_m1_pumpe_reduziert_e9', 0x27E9, 1, 1, False),

    ('SLOW', 'heizkreis_m1_estrichfunktion_f1', 0x27F1, 1, 1, False),
    ('SLOW', 'heizkreis_m1_party_zeitbegrenzung_f2', 0x27F2, 1, 1, False),
    ('SLOW', 'heizkreis_m1_reduziert_anhebung_start_f8', 0x27F8, 1, 1, True),
    ('SLOW', 'heizkreis_m1_reduziert_anhebung_ende_f9', 0x27F9, 1, 1, True),
    ('SLOW', 'heizkreis_m1_vorlauf_ueberhoehung_fa', 0x27FA, 1, 1, False),
    ('SLOW', 'heizkreis_m1_vorlauf_ueberhoehung_dauer_fb', 0x27FB, 1, 2, False),

    # ---------------------------------------------------------------------
    # Boiler / DHW service coding
    # ---------------------------------------------------------------------
    ('SLOW', 'kessel_maximaltemperatur_06', 0x5706, 1, 1, False),
    ('SLOW', 'interne_pumpe_kennung_30', 0x5730, 1, 1, False),
    ('SLOW', 'interne_pumpe_solldrehzahl_31', 0x5731, 1, 1, False),

    ('SLOW', 'warmwasser_kessel_offset_60', 0x6760, 1, 1, False),
    ('SLOW', 'warmwasser_pumpennachlauf_62', 0x6762, 2, 1, False),
    ('SLOW', 'umschaltventil_bauart_65', 0x6765, 1, 1, False),

    ('SLOW', 'zirkulation_bei_ww_soll1_71', 0x6771, 1, 1, False),
    ('SLOW', 'zirkulation_bei_ww_soll2_72', 0x6772, 1, 1, False),
    ('SLOW', 'zirkulation_intervall_73', 0x6773, 1, 1, False),
    ('SLOW', 'relais_k12_funktion_53', 0x7753, 1, 1, False),

    # ---------------------------------------------------------------------
    # Counters / system time / errors
    # ---------------------------------------------------------------------
    ('RARE', 'brenner_starts', 0x088A, 4, 1, True),
    ('RARE', 'brenner_betriebsstunden', 0x08A7, 4, 0.0002777777777777778, False),
    ('RARE', 'brenner_betriebsstunden_stufe1', 0x0886, 4, 0.0002777777777777778, False),
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

    # ---------------------------------------------------------------------
    # Time programs
    # ---------------------------------------------------------------------
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

    # ---------------------------------------------------------------------
    # Optional M2 heating circuit
    # ---------------------------------------------------------------------
    ('OPTIONAL_M2', 'heizkreis_m2_sparbetrieb', 0x3302, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_partybetrieb', 0x3303, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_raumtemperatur', 0x0898, 2, 0.1, True),
    ('OPTIONAL_M2', 'heizkreis_m2_vorlauftemperatur', 0x3900, 2, 0.1, True),
    ('OPTIONAL_M2', 'heizkreis_m2_vorlaufsolltemperatur', 0x3544, 2, 0.1, True),
    ('OPTIONAL_M2', 'heizkreis_m2_pumpe_status', 0x3906, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_pumpe_drehzahl', 0x7665, 2, 'b:1:1', 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_vorlauf_min_c5', 0x37C5, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_vorlauf_max_c6', 0x37C6, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_heizkennlinie_neigung_d3', 0x37D3, 1, 0.1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_heizkennlinie_niveau_d4', 0x37D4, 1, 1, True),

    # ---------------------------------------------------------------------
    # Optional solar
    # ---------------------------------------------------------------------
    ('OPTIONAL_SOLAR', 'solar_kollektortemperatur', 0x6564, 2, 0.1, True),
    ('OPTIONAL_SOLAR', 'solar_speichertemperatur', 0x6566, 2, 0.1, True),
    ('OPTIONAL_SOLAR', 'solarpumpe_status', 0x6552, 1, 1, False),
    ('OPTIONAL_SOLAR', 'solarpumpe_betriebsstunden', 0x6568, 2, 1, False),
    ('OPTIONAL_SOLAR', 'solarenergie', 0x6560, 4, 1, False),

    # ---------------------------------------------------------------------
    # Experimental / not yet promoted
    # ---------------------------------------------------------------------
    ('EXPERIMENTAL', 'sammelstoerung_relais_raw', 0xA152, 2, 'b:0:1:0x0001:big', 'bool', False),
]

# -----------------------------------------------------------------------------
# Deliberately NOT exposed as write controls yet
# -----------------------------------------------------------------------------
#
# Party / economy:
#   VDensHO1 clearly exposes read state at 0x2303 / 0x2302. The exact safe
#   write path for this old firmware is still to be hardware-verified.
#
# Circulation pump:
#   0x6515 is status. 0x0842 is relay K12 status. Time programs and coding
#   71/72/73 are documented. A direct "run now" command is not exposed yet.
#
# Burner unlock/reset:
#   lockout is readable from 0x55D3. No defensible VDensHO1 P300 write command
#   for fire-control unlock has been identified. K24/0x5724 is a maintenance
#   status reset and must NOT be confused with burner fault unlock.
#
# Fan speed:
#   the VDensHO1 Vitosoft export contains fire-control process data that are
#   filtered out of the standard Optolink-readable catalog because they require
#   a non-Virtual_READ access method. Therefore no guessed fan-RPM poll item is
#   enabled here. 0x0B1C/0x0B1E remain community candidates for later manual
#   probing. On this exact 20C2/0x03 controller, both 0x0B1C and 0x0B1E
#   returned P300 error telegrams (retcode 3 / payload 0x01) for len=2, so
#   they are not usable as ordinary VDensHO1 Virtual_READ datapoints.
