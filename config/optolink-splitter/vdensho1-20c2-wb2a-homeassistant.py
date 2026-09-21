"""
Home Assistant / MQTT discovery profile for the verified boiler profile:

  Viessmann Vitodens 200-W WB2A
  VDensHO1 / device id 0x20C2
  software index 0x03

This is the live image profile installed as /opt/optolink/homeassistant_poll_list.py.
The legacy /opt/optolink/poll_list.py is removed when this profile is applied
because optolink-splitter gives poll_list.py precedence over the HA adapter.

Hardware research source of truth:
  vdensho1-20c2-wb2a-service-draft-poll-list.py

Policy used here:
  * expose hardware-verified read datapoints;
  * expose writes only where this exact appliance has accepted the write and
    the resulting controller state has been verified;
  * keep absent hardware (M2, solar, hydraulic separator, invalid sensor
    inputs) out of productive polling;
  * keep diagnostics/service values enabled for use in dashboards/automations,\n    but hidden by default from generated UI where possible;
  * do not expose burner unlock/reset;
  * do not expose economy mode as a switch: 0x2302 write ACKs but is ignored.

Write verification on this exact appliance:
  0x2303 party mode: R/W 0/1
  0x2306 normal room target: R/W
  0x2307 reduced room target: R/W
  0x2308 party room target: R/W
  0x2323 operating mode: R/W verified for values 2 and 4
  0x6300 DHW target: R/W, current configured range 10..60 C
  0x6773 circulation interval: R/W verified for values 0 and 7

Writable selects expose the complete VDensHO1 source-documented enums.
Hardware write tests on this exact appliance have so far covered 0x2323
values 2 and 4, and 0x6773 values 0 and 7.
"""

poll_list = {
    "device": {
        "identifiers": ["viessmann_vitodens_200_w_wb2a_20c2"],
        "name": "Vitodens 200-W WB2A",
        "model": "Vitodens 200-W WB2A",
        "manufacturer": "Viessmann",
        "hw_version": "20C2",
        "sw_version": "VDensHO1 SW03",
    },

    "node_id": "vitodens_200_w_wb2a_20c2",
    "dp_prefix": "vitodens_200_wb2a_",

    "beautifier": {
        "search": [
            "aussentemperatur", "kessel", "warmwasser", "heizkreis_m1",
            "brenner", "pumpe", "zirkulation", "betriebsart", "solltemperatur",
            "temperatur", "ueber", "stoer", "geraete"
        ],
        "replace": [
            "außentemperatur", "kessel", "warmwasser", "heizkreis m1",
            "brenner", "pumpe", "zirkulation", "betriebsart", "solltemperatur",
            "temperatur", "über", "stör", "geräte"
        ],
        "fixed": ["WW", "A1", "M1", "K12", "GFA", "SW"],
    },

    "poll_interval": 2,
    "poll_groups": {
        "ONCE": 0,
        "FAST": 1,       # ~2 s
        "NORMAL": 15,    # ~30 s
        "SLOW": 150,     # ~5 min
        "RARE": 900,     # ~30 min
        "DISABLED": -1,
    },

    "mqtt_delay": 0.15,

    "domains": [
        # -----------------------------------------------------------------
        # Temperatures
        # -----------------------------------------------------------------
        {
            "domain": "sensor",
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
            "suggested_display_precision": 1,
            "poll": [
                ("FAST",   "aussentemperatur",                   0x0800, 2, 0.1, True),
                ("NORMAL", "aussentemperatur_tiefpass",          0x5525, 2, 0.1, True),
                ("NORMAL", "aussentemperatur_gedaempft",         0x5527, 2, 0.1, True),
                ("FAST",   "kesseltemperatur",                   0x0810, 2, 0.1, True),
                ("FAST",   "kessel_solltemperatur_effektiv",     0x555A, 2, 0.1, True),
                ("NORMAL", "abgastemperatur",                    0x0816, 2, 0.1, True),
                ("FAST",   "warmwasser_temperatur",              0x0812, 2, 0.1, True),
                ("NORMAL", "warmwasser_solltemperatur_aktuell",  0x6500, 2, 0.1, True),
                ("FAST",   "heizkreis_m1_vorlauftemperatur",     0x2900, 2, 0.1, True),
                ("FAST",   "heizkreis_m1_vorlaufsolltemperatur", 0x2544, 2, 0.1, True),
                ("NORMAL", "heizkreis_m1_raumsolltemperatur_aktuell",
                                                                  0x2500, 22, "b:12:13", 0.1, True),
            ],
        },

        # -----------------------------------------------------------------
        # Percentages
        # -----------------------------------------------------------------
        {
            "domain": "sensor",
            "unit_of_measurement": "%",
            "state_class": "measurement",
            "suggested_display_precision": 0,
            "poll": [
                ("FAST", "brenner_modulationsgrad",         0xA305, 1, 0.5, False),
                ("FAST", "interne_pumpe_drehzahl",          0x7660, 2, "b:1:1", 1, False),
                ("FAST", "heizkreis_m1_pumpe_drehzahl",     0x7663, 2, "b:1:1", 1, False),
            ],
        },

        # -----------------------------------------------------------------
        # Counters
        # -----------------------------------------------------------------
        {
            "domain": "sensor",
            "state_class": "total_increasing",
            "icon": "mdi:counter",
            "poll": [
                ("RARE", "brenner_starts", 0x088A, 4, 1, False),
            ],
        },
        {
            "domain": "sensor",
            "unit_of_measurement": "h",
            "device_class": "duration",
            "state_class": "total_increasing",
            "suggested_display_precision": 1,
            "units": [
                {
                    "poll": [
                        ("RARE", "brenner_betriebsstunden", 0x08A7, 4, 0.0002777777777777778, False),
                    ],
                },
                {
                    "enabled_by_default": True,
                    "visible_by_default": False,
                    "poll": [
                        ("RARE", "brenner_betriebsstunden_stufe1", 0x0886, 4, 0.0002777777777777778, False),
                    ],
                },
            ],
        },

        # -----------------------------------------------------------------
        # Binary status: numeric 0/1
        # -----------------------------------------------------------------
        {
            "domain": "binary_sensor",
            "payload_on": "1",
            "payload_off": "0",
            "poll": [
                ("FAST",   "interne_pumpe_status",              0x7660, 2, "b:0:0", 1, False),
                ("FAST",   "heizkreis_m1_pumpe_ausgang",        0x7663, 2, "b:0:0", 1, False),
                ("FAST",   "heizkreis_m1_pumpe_logisch",        0x2906, 1, 1, False),
                ("FAST",   "speicherladepumpe_status",          0x6513, 1, 1, False),
                ("FAST",   "zirkulationspumpe_status",          0x6515, 1, 1, False),
                ("NORMAL", "warmwasser_flowswitch",             0x0883, 1, 1, False),
                ("NORMAL", "heizkreis_m1_sparbetrieb",          0x2302, 1, 1, False),
            ],
        },
        {
            "domain": "binary_sensor",
            "payload_on": "1",
            "payload_off": "0",
            "entity_category": "diagnostic",
            "enabled_by_default": True,
            "visible_by_default": False,
            "poll": [
                ("FAST", "relais_k12_status", 0x0842, 1, 1, False),
            ],
        },

        # -----------------------------------------------------------------
        # Binary status: bit filters formatted as True/False by splitter
        # -----------------------------------------------------------------
        {
            "domain": "binary_sensor",
            "payload_on": "True",
            "payload_off": "False",
            "poll": [
                ("FAST",   "brenner_flamme",              0x55D3, 9, "b:5:5:0x20", "bool", False),
                ("NORMAL", "heizkreis_m1_frostgefahr",    0x2500, 22, "b:16:16:0x01", "bool", False),
                ("NORMAL", "heizkreis_m1_ferienbetrieb",   0x2535, 1, "b:0:0:0x01", "bool", False),
            ],
        },
        {
            "domain": "binary_sensor",
            "payload_on": "True",
            "payload_off": "False",
            "device_class": "problem",
            "entity_category": "diagnostic",
            "poll": [
                ("FAST", "feuerungsautomat_verriegelt", 0x55D3, 9, "b:5:5:0x40", "bool", False),
            ],
        },
        {
            "domain": "binary_sensor",
            "payload_on": "True",
            "payload_off": "False",
            "entity_category": "diagnostic",
            "enabled_by_default": True,
            "visible_by_default": False,
            "poll": [
                ("NORMAL", "brenner_flamme_gfa", 0x55DD, 1, "b:0:0:0x20", "bool", False),
            ],
        },

        # -----------------------------------------------------------------
        # Party mode: hardware-verified R/W
        # -----------------------------------------------------------------
        {
            "domain": "switch",
            "icon": "mdi:party-popper",
            "command_topic": "%mqtt_listen%",
            "payload_on": "1",
            "payload_off": "0",
            "state_on": "1",
            "state_off": "0",
            "command_template": "{% if value == '1' %}w;%DpAddr%;%Length%;1{% else %}w;%DpAddr%;%Length%;0{% endif %}",
            "optimistic": False,
            "poll": [
                ("NORMAL", "heizkreis_m1_partybetrieb", 0x2303, 1, 1, False),
            ],
        },

        # -----------------------------------------------------------------
        # Writable room/DHW setpoints: all hardware-verified R/W
        # -----------------------------------------------------------------
        {
            "domain": "number",
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "suggested_display_precision": 0,
            "step": 1,
            "mode": "box",
            "command_topic": "%mqtt_listen%",
            "command_template": "{{ 'w;%DpAddr%;%Length%;' ~ (value | int) }}",
            "units": [
                {
                    "min": 3,
                    "max": 37,
                    "poll": [
                        ("NORMAL", "heizkreis_m1_raumsolltemperatur_normal",     0x2306, 1, 1, False),
                        ("NORMAL", "heizkreis_m1_raumsolltemperatur_reduziert", 0x2307, 1, 1, False),
                        ("NORMAL", "heizkreis_m1_raumsolltemperatur_party",     0x2308, 1, 1, False),
                    ],
                },
                {
                    # 0x6756=0 configures the user range to 10..60 C.
                    # Coding-plug capability at 0x1050 is 10..63 C.
                    "min": 10,
                    "max": 60,
                    "poll": [
                        ("NORMAL", "warmwasser_solltemperatur", 0x6300, 1, 1, False),
                    ],
                },
            ],
        },

        # -----------------------------------------------------------------
        # Operating mode 0x2323.
        # Exact VDensHO1 enum. Hardware writes verified on this unit for 2 <-> 4.
        # -----------------------------------------------------------------
        {
            "domain": "select",
            "options": [
                "Abschalt",
                "Nur WW",
                "Heizen + WW",
                "Dauernd Reduziert",
                "Dauernd Normal",
            ],
            "command_topic": "%mqtt_listen%",
            "command_template": "{% if value == 'Abschalt' %}w;%DpAddr%;%Length%;0{% elif value == 'Nur WW' %}w;%DpAddr%;%Length%;1{% elif value == 'Heizen + WW' %}w;%DpAddr%;%Length%;2{% elif value == 'Dauernd Reduziert' %}w;%DpAddr%;%Length%;3{% elif value == 'Dauernd Normal' %}w;%DpAddr%;%Length%;4{% endif %}",
            "value_template": "{% set v = value | int(-1) %}{% if v == 0 %}Abschalt{% elif v == 1 %}Nur WW{% elif v == 2 %}Heizen + WW{% elif v == 3 %}Dauernd Reduziert{% elif v == 4 %}Dauernd Normal{% else %}Unbekannt ({{ v }}){% endif %}",
            "optimistic": False,
            "poll": [
                ("NORMAL", "heizkreis_m1_betriebsart", 0x2323, 1, 1, False),
            ],
        },

        # -----------------------------------------------------------------
        # Circulation interval 0x6773.
        # Exact VDensHO1 enum. Hardware writes verified on this unit for 0 <-> 7.
        # -----------------------------------------------------------------
        {
            "domain": "select",
            "options": [
                "Schaltuhr",
                "1 pro Stunde",
                "2 pro Stunde",
                "3 pro Stunde",
                "4 pro Stunde",
                "5 pro Stunde",
                "6 pro Stunde",
                "EIN",
            ],
            "command_topic": "%mqtt_listen%",
            "command_template": "{% if value == 'Schaltuhr' %}w;%DpAddr%;%Length%;0{% elif value == '1 pro Stunde' %}w;%DpAddr%;%Length%;1{% elif value == '2 pro Stunde' %}w;%DpAddr%;%Length%;2{% elif value == '3 pro Stunde' %}w;%DpAddr%;%Length%;3{% elif value == '4 pro Stunde' %}w;%DpAddr%;%Length%;4{% elif value == '5 pro Stunde' %}w;%DpAddr%;%Length%;5{% elif value == '6 pro Stunde' %}w;%DpAddr%;%Length%;6{% elif value == 'EIN' %}w;%DpAddr%;%Length%;7{% endif %}",
            "value_template": "{% set v = value | int(-1) %}{% if v == 0 %}Schaltuhr{% elif v == 1 %}1 pro Stunde{% elif v == 2 %}2 pro Stunde{% elif v == 3 %}3 pro Stunde{% elif v == 4 %}4 pro Stunde{% elif v == 5 %}5 pro Stunde{% elif v == 6 %}6 pro Stunde{% elif v == 7 %}EIN{% else %}Unbekannt ({{ v }}){% endif %}",
            "optimistic": False,
            "poll": [
                ("SLOW", "zirkulation_intervall", 0x6773, 1, 1, False),
            ],
        },

        # -----------------------------------------------------------------
        # Service/config controls used by the Home Assistant dashboard.
        #
        # These controls reuse already-polled datapoints via MQTT /set topics,
        # so they add no duplicate Optolink reads. The ranges below follow the
        # VDensHO1/Viessmann coding documentation. They are source-documented
        # R/W controls, but (unless noted above) have not all been hardware-
        # write-tested on this exact appliance.
        # -----------------------------------------------------------------
        {
            "domain": "number",
            "entity_category": "config",
            "mode": "box",
            "units": [
                {
                    "min": 0.2,
                    "max": 3.5,
                    "step": 0.1,
                    "nopoll": [
                        {
                            "name": "heizkreis_m1_heizkennlinie_neigung_d3",
                            "command_topic": "{mqtt_base}/heizkreis_m1_heizkennlinie_neigung_d3/set",
                        },
                    ],
                },
                {
                    "min": -13,
                    "max": 40,
                    "step": 1,
                    "unit_of_measurement": "K",
                    "nopoll": [
                        {
                            "name": "heizkreis_m1_heizkennlinie_niveau_d4",
                            "command_topic": "{mqtt_base}/heizkreis_m1_heizkennlinie_niveau_d4/set",
                        },
                    ],
                },
                {
                    "min": -9,
                    "max": 15,
                    "step": 1,
                    "unit_of_measurement": "°C",
                    "nopoll": [
                        {
                            "name": "heizkreis_m1_frostgrenze_a3",
                            "command_topic": "{mqtt_base}/heizkreis_m1_frostgrenze_a3/set",
                        },
                    ],
                },
                {
                    "min": 0,
                    "max": 15,
                    "step": 1,
                    "nopoll": [
                        {
                            "name": "heizkreis_m1_sommerspar_schaltschwelle_a5",
                            "command_topic": "{mqtt_base}/heizkreis_m1_sommerspar_schaltschwelle_a5/set",
                        },
                    ],
                },
                {
                    "min": 5,
                    "max": 36,
                    "step": 1,
                    "unit_of_measurement": "°C",
                    "nopoll": [
                        {
                            "name": "heizkreis_m1_sommersparabschaltung_a6",
                            "command_topic": "{mqtt_base}/heizkreis_m1_sommersparabschaltung_a6/set",
                        },
                    ],
                },
                {
                    "min": 1,
                    "max": 127,
                    "step": 1,
                    "unit_of_measurement": "°C",
                    "nopoll": [
                        {
                            "name": "heizkreis_m1_vorlauf_min_c5",
                            "command_topic": "{mqtt_base}/heizkreis_m1_vorlauf_min_c5/set",
                        },
                    ],
                },
                {
                    "min": 10,
                    "max": 127,
                    "step": 1,
                    "unit_of_measurement": "°C",
                    "nopoll": [
                        {
                            "name": "heizkreis_m1_vorlauf_max_c6",
                            "command_topic": "{mqtt_base}/heizkreis_m1_vorlauf_max_c6/set",
                        },
                    ],
                },
                {
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "unit_of_measurement": "%",
                    "nopoll": [
                        {
                            "name": "heizkreis_m1_pumpe_max_drehzahl_e6",
                            "command_topic": "{mqtt_base}/heizkreis_m1_pumpe_max_drehzahl_e6/set",
                        },
                        {
                            "name": "heizkreis_m1_pumpe_min_drehzahl_e7",
                            "command_topic": "{mqtt_base}/heizkreis_m1_pumpe_min_drehzahl_e7/set",
                        },
                        {
                            "name": "heizkreis_m1_pumpe_reduziert_e9",
                            "command_topic": "{mqtt_base}/heizkreis_m1_pumpe_reduziert_e9/set",
                        },
                        {
                            "name": "interne_pumpe_solldrehzahl_31",
                            "command_topic": "{mqtt_base}/interne_pumpe_solldrehzahl_31/set",
                        },
                    ],
                },
                {
                    "min": 0,
                    "max": 15,
                    "step": 1,
                    "unit_of_measurement": "min",
                    "nopoll": [
                        {
                            "name": "heizkreis_m1_pumpe_reduziert_a9",
                            "command_topic": "{mqtt_base}/heizkreis_m1_pumpe_reduziert_a9/set",
                        },
                        {
                            "name": "warmwasser_pumpennachlauf_62",
                            "command_topic": "{mqtt_base}/warmwasser_pumpennachlauf_62/set",
                        },
                    ],
                },
                {
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "unit_of_measurement": "K",
                    "nopoll": [
                        {
                            "name": "warmwasser_einschalt_offset_59",
                            "command_topic": "{mqtt_base}/warmwasser_einschalt_offset_59/set",
                        },
                    ],
                },
                {
                    "min": 5,
                    "max": 25,
                    "step": 1,
                    "unit_of_measurement": "K",
                    "nopoll": [
                        {
                            "name": "warmwasser_kessel_offset_60",
                            "command_topic": "{mqtt_base}/warmwasser_kessel_offset_60/set",
                        },
                    ],
                },
            ],
        },
        {
            "domain": "select",
            "entity_category": "config",
            "options": [
                "Minimum nach E7",
                "Reduziert nach E9",
            ],
            "command_template": "{% if value == 'Minimum nach E7' %}0{% elif value == 'Reduziert nach E9' %}1{% endif %}",
            "value_template": "{% set v = value | int(-1) %}{% if v == 0 %}Minimum nach E7{% elif v == 1 %}Reduziert nach E9{% else %}Unbekannt ({{ v }}){% endif %}",
            "nopoll": [
                {
                    "name": "heizkreis_m1_pumpe_nebenbetrieb_e8",
                    "command_topic": "{mqtt_base}/heizkreis_m1_pumpe_nebenbetrieb_e8/set",
                },
            ],
        },
        {
            "domain": "select",
            "entity_category": "config",
            "options": [
                "Nach Zeitprogramm",
                "Aus bei WW-Ladung",
                "Ein bei WW-Ladung",
            ],
            "command_template": "{% if value == 'Nach Zeitprogramm' %}0{% elif value == 'Aus bei WW-Ladung' %}1{% elif value == 'Ein bei WW-Ladung' %}2{% endif %}",
            "value_template": "{% set v = value | int(-1) %}{% if v == 0 %}Nach Zeitprogramm{% elif v == 1 %}Aus bei WW-Ladung{% elif v == 2 %}Ein bei WW-Ladung{% else %}Unbekannt ({{ v }}){% endif %}",
            "nopoll": [
                {
                    "name": "zirkulation_bei_ww_soll1_71",
                    "command_topic": "{mqtt_base}/zirkulation_bei_ww_soll1_71/set",
                },
                {
                    "name": "zirkulation_bei_ww_soll2_72",
                    "command_topic": "{mqtt_base}/zirkulation_bei_ww_soll2_72/set",
                },
            ],
        },

        # -----------------------------------------------------------------
        # Enumerated operating/status sensors
        # -----------------------------------------------------------------
        {
            "domain": "sensor",
            "poll": [],
            "units": [
                {
                    "value_template": "{% set v = value | int(-1) %}{% if v == 0 %}Abschaltbetrieb{% elif v == 1 %}Reduzierter Betrieb{% elif v == 2 %}Normalbetrieb{% elif v == 3 %}Dauernd Normal{% else %}Wert {{ v }}{% endif %}",
                    "poll": [
                        ("NORMAL", "heizkreis_m1_betriebsart_aktuell", 0x2500, 22, "b:1:1", 1, False),
                    ],
                },
                {
                    "value_template": "{% set v = value | int(-1) %}{% if v == 2 %}Normal dauernd{% elif v == 3 %}Heizen + WW Schaltzeiten{% else %}Wert {{ v }}{% endif %}",
                    "poll": [
                        ("NORMAL", "heizkreis_m1_betriebsprogramm_aktuell", 0x2301, 1, 1, False),
                    ],
                },
                {
                    "value_template": "{% set v = value | int(-1) %}{% if v == 0 %}Ladung inaktiv{% elif v == 1 %}In Ladung{% elif v == 2 %}Im Nachlauf{% else %}Wert {{ v }}{% endif %}",
                    "poll": [
                        ("FAST", "warmwasser_ladestatus", 0x650A, 1, 1, False),
                    ],
                },
                {
                    "value_template": "{% set v = value | int(-1) %}{% if v == 0 %}Undefiniert{% elif v == 1 %}Richtung Heizen{% elif v == 2 %}Mittelstellung{% elif v == 3 %}Richtung Warmwasser{% else %}Wert {{ v }}{% endif %}",
                    "poll": [
                        ("FAST", "umschaltventil_stellung", 0x0A10, 1, 1, False),
                    ],
                },
            ],
        },

        # -----------------------------------------------------------------
        # Sensor/control diagnostics
        # -----------------------------------------------------------------
        {
            "domain": "sensor",
            "entity_category": "diagnostic",
            "enabled_by_default": True,
            "visible_by_default": False,
            "units": [
                {
                    "value_template": "{% set v = value | int(-1) %}{% if v == 0 %}OK{% elif v == 1 %}Kurzschluss{% elif v == 2 %}Unterbrechung{% elif v == 3 %}Referenzfehler{% elif v == 4 %}Referenzfehler 0x04{% elif v == 5 %}Sensorstatus 5{% elif v == 6 %}Nicht vorhanden{% else %}Wert {{ v }}{% endif %}",
                    "poll": [
                        ("SLOW", "sensorstatus_aussentemperatur", 0x083A, 1, 1, False),
                        ("SLOW", "sensorstatus_kesseltemperatur", 0x083B, 1, 1, False),
                        ("SLOW", "sensorstatus_sts2",             0x083D, 1, 1, False),
                        ("SLOW", "sensorstatus_vlts",             0x0840, 1, 1, False),
                        ("SLOW", "sensorstatus_raum_m1",          0x089C, 1, 1, False),
                    ],
                },
                {
                    "value_template": "{% set v = value | int(-1) %}{% if v == 0 %}Konstantregelung{% elif v == 1 %}VT-Soll über LON{% elif v == 2 %}Witterungsgeführt{% elif v == 3 %}Raumregelung{% elif v == 4 %}Estrichprogramm{% elif v == 5 %}Heizkreis nicht vorhanden{% else %}Wert {{ v }}{% endif %}",
                    "poll": [
                        ("ONCE", "heizkreis_m1_reglervariante", 0x2521, 1, 1, False),
                    ],
                },
            ],
        },

        # -----------------------------------------------------------------
        # Service values - read only, diagnostic, enabled but hidden by default.
        # -----------------------------------------------------------------
        {
            "domain": "sensor",
            "entity_category": "diagnostic",
            "enabled_by_default": True,
            "visible_by_default": False,
            "units": [
                {
                    "unit_of_measurement": "°C",
                    "poll": [
                        ("SLOW", "heizkreis_m1_frostgrenze_a3", 0x27A3, 1, 1, True),
                        ("SLOW", "heizkreis_m1_sommersparabschaltung_a6", 0x27A6, 1, 1, False),
                        ("SLOW", "heizkreis_m1_vorlauf_min_c5", 0x27C5, 1, 1, False),
                        ("SLOW", "heizkreis_m1_vorlauf_max_c6", 0x27C6, 1, 1, False),
                        ("SLOW", "kessel_maximaltemperatur_06", 0x5706, 1, 1, False),
                    ],
                },
                {
                    "unit_of_measurement": "K",
                    "poll": [
                        ("SLOW", "heizkreis_m1_heizkennlinie_niveau_d4", 0x27D4, 1, 1, True),
                        ("SLOW", "warmwasser_kessel_offset_60", 0x6760, 1, 1, False),
                    ],
                },
                {
                    "unit_of_measurement": "%",
                    "poll": [
                        ("SLOW", "heizkreis_m1_pumpe_max_drehzahl_e6", 0x27E6, 1, 1, False),
                        ("SLOW", "heizkreis_m1_pumpe_min_drehzahl_e7", 0x27E7, 1, 1, False),
                        ("SLOW", "heizkreis_m1_pumpe_reduziert_e9",    0x27E9, 1, 1, False),
                        ("SLOW", "interne_pumpe_solldrehzahl_31",      0x5731, 1, 1, False),
                    ],
                },
                {
                    "unit_of_measurement": "min",
                    "poll": [
                        ("SLOW", "heizkreis_m1_pumpe_reduziert_a9", 0x27A9, 1, 1, False),
                        ("SLOW", "warmwasser_pumpennachlauf_62",     0x6762, 1, 1, False),
                    ],
                },
                {
                    "poll": [
                        ("SLOW", "heizkreis_m1_speichervorrang_a2",         0x27A2, 1, 1, False),
                        ("SLOW", "heizkreis_m1_frostschutz_a4",             0x27A4, 1, 1, False),
                        ("SLOW", "heizkreis_m1_sommerspar_schaltschwelle_a5",0x27A5, 1, 1, False),
                        ("SLOW", "heizkreis_m1_mischersparfunktion_a7",      0x27A7, 1, 1, False),
                        ("SLOW", "heizkreis_m1_heizkennlinie_neigung_d3",    0x27D3, 1, 0.1, False),
                        ("SLOW", "heizkreis_m1_pumpentyp_e5",                0x27E5, 1, 1, False),
                        ("SLOW", "heizkreis_m1_pumpe_nebenbetrieb_e8",       0x27E8, 1, 1, False),
                        ("SLOW", "heizkreis_m1_temperaturprogramm_f1",       0x27F1, 1, 1, False),
                        ("SLOW", "heizkreis_m1_party_zeitbegrenzung_f2",     0x27F2, 1, 1, False),
                        ("SLOW", "interne_pumpe_kennung_30",                 0x5730, 1, 1, False),
                        ("SLOW", "warmwasser_sollbereich_56",                0x6756, 1, 1, False),
                        ("SLOW", "warmwasser_einschalt_offset_59",           0x6759, 1, 1, False),
                        ("SLOW", "warmwasser_speicher_anbindung_5b",         0x675B, 1, 1, False),
                        ("SLOW", "umschaltventil_bauart_65",                 0x6765, 1, 1, False),
                        ("SLOW", "zirkulation_bei_ww_soll1_71",             0x6771, 1, 1, False),
                        ("SLOW", "zirkulation_bei_ww_soll2_72",             0x6772, 1, 1, False),
                        ("SLOW", "relais_k12_funktion_53",                   0x7753, 1, 1, False),
                    ],
                },
            ],
        },

        # -----------------------------------------------------------------
        # Identification/topology - diagnostics
        # -----------------------------------------------------------------
        {
            "domain": "sensor",
            "entity_category": "diagnostic",
            "enabled_by_default": True,
            "visible_by_default": False,
            "units": [
                {
                    "poll": [
                        ("ONCE", "geraete_id",                     0x00F8, 8, "raw"),
                        ("ONCE", "codierstecker_sachnummer",       0x1010, 7, "utf8"),
                        ("ONCE", "codierstecker_kennung",          0x1040, 2, "raw"),
                        ("ONCE", "bedienteil_sw_index",            0x7330, 1, 1, False),
                        ("ONCE", "gfa_kennung",                    0x7650, 1, 1, False),
                        ("ONCE", "anlagenschema",                  0x7700, 1, 1, False),
                        ("ONCE", "anlagentyp",                     0x7701, 1, 1, False),
                        ("ONCE", "bauart_warmwasser",              0x8851, 1, 1, False),
                        ("ONCE", "hydraulische_weiche_vorhanden", 0x7752, 1, 1, False),
                        ("ONCE", "solar_typ",                      0x7754, 1, 1, False),
                    ],
                },
            ],
        },

        # -----------------------------------------------------------------
        # System clock
        # -----------------------------------------------------------------
        {
            "domain": "sensor",
            "entity_category": "diagnostic",
            "enabled_by_default": True,
            "visible_by_default": False,
            "icon": "mdi:clock-outline",
            "poll": [
                ("RARE", "systemzeit", 0x088E, 8, "vdatetime"),
            ],
        },

        # -----------------------------------------------------------------
        # Fault history. The current poll value is the first-byte fault code.
        # Full 9-byte timestamp decoding stays in the research profile.
        # -----------------------------------------------------------------
        {
            "domain": "sensor",
            "entity_category": "diagnostic",
            "enabled_by_default": True,
            "visible_by_default": False,
            "icon": "mdi:alert-circle-outline",
            "poll": [
                ("RARE", "fehlerhistorie_01", 0x7507, 9, "b:0:0", "f:02X", False),
                ("RARE", "fehlerhistorie_02", 0x7510, 9, "b:0:0", "f:02X", False),
                ("RARE", "fehlerhistorie_03", 0x7519, 9, "b:0:0", "f:02X", False),
                ("RARE", "fehlerhistorie_04", 0x7522, 9, "b:0:0", "f:02X", False),
                ("RARE", "fehlerhistorie_05", 0x752B, 9, "b:0:0", "f:02X", False),
                ("RARE", "fehlerhistorie_06", 0x7534, 9, "b:0:0", "f:02X", False),
                ("RARE", "fehlerhistorie_07", 0x753D, 9, "b:0:0", "f:02X", False),
                ("RARE", "fehlerhistorie_08", 0x7546, 9, "b:0:0", "f:02X", False),
                ("RARE", "fehlerhistorie_09", 0x754F, 9, "b:0:0", "f:02X", False),
                ("RARE", "fehlerhistorie_10", 0x7558, 9, "b:0:0", "f:02X", False),
            ],
        },

        # -----------------------------------------------------------------
        # Time programs - read only in this HA draft.
        # schedvdens is supported by current optolink-splitter.
        # -----------------------------------------------------------------
        {
            "domain": "sensor",
            "entity_category": "diagnostic",
            "enabled_by_default": True,
            "visible_by_default": False,
            "icon": "mdi:calendar-clock",
            "poll": [
                ("RARE", "heizkreis_m1_zeitprogramm_montag",     0x2000, 8, "schedvdens"),
                ("RARE", "heizkreis_m1_zeitprogramm_dienstag",   0x2008, 8, "schedvdens"),
                ("RARE", "heizkreis_m1_zeitprogramm_mittwoch",   0x2010, 8, "schedvdens"),
                ("RARE", "heizkreis_m1_zeitprogramm_donnerstag", 0x2018, 8, "schedvdens"),
                ("RARE", "heizkreis_m1_zeitprogramm_freitag",    0x2020, 8, "schedvdens"),
                ("RARE", "heizkreis_m1_zeitprogramm_samstag",    0x2028, 8, "schedvdens"),
                ("RARE", "heizkreis_m1_zeitprogramm_sonntag",    0x2030, 8, "schedvdens"),

                ("RARE", "warmwasser_zeitprogramm_montag",       0x2100, 8, "schedvdens"),
                ("RARE", "warmwasser_zeitprogramm_dienstag",     0x2108, 8, "schedvdens"),
                ("RARE", "warmwasser_zeitprogramm_mittwoch",     0x2110, 8, "schedvdens"),
                ("RARE", "warmwasser_zeitprogramm_donnerstag",   0x2118, 8, "schedvdens"),
                ("RARE", "warmwasser_zeitprogramm_freitag",      0x2120, 8, "schedvdens"),
                ("RARE", "warmwasser_zeitprogramm_samstag",      0x2128, 8, "schedvdens"),
                ("RARE", "warmwasser_zeitprogramm_sonntag",      0x2130, 8, "schedvdens"),

                ("RARE", "zirkulation_zeitprogramm_montag",      0x2200, 8, "schedvdens"),
                ("RARE", "zirkulation_zeitprogramm_dienstag",    0x2208, 8, "schedvdens"),
                ("RARE", "zirkulation_zeitprogramm_mittwoch",    0x2210, 8, "schedvdens"),
                ("RARE", "zirkulation_zeitprogramm_donnerstag",  0x2218, 8, "schedvdens"),
                ("RARE", "zirkulation_zeitprogramm_freitag",     0x2220, 8, "schedvdens"),
                ("RARE", "zirkulation_zeitprogramm_samstag",     0x2228, 8, "schedvdens"),
                ("RARE", "zirkulation_zeitprogramm_sonntag",     0x2230, 8, "schedvdens"),
            ],
        },
    ],
}

# Intentionally omitted from this live HA profile:
#
# * 0x2302 as writable economy switch:
#     hardware write ACK is ignored by the controller.
#
# * M2, solar, hydraulic-separator values:
#     hardware/configuration proves these options are absent.
#
# * 0x081A VTS/VLTS, 0x0814 STS2, 0x0896 room temperature:
#     corresponding sensor-status datapoints report invalid/open/reference
#     states; their 20.0 C values are defaults, not physical measurements.
#
# * Fan speed:
#     0x0B1C / 0x0B1E return P300 error on this SW03 controller.
#
# * Burner reset/unlock:
#     no defensible ordinary VDensHO1 P300 write datapoint is known.
#
# * Water-heater/climate aggregate entities:
#     intentionally deferred until their mode semantics are tested as a unit.
#
# * Select write coverage:
#     Full exact-catalog enums are exposed. Hardware write tests on this exact
#     appliance currently cover 0x2323 values 2/4 and 0x6773 values 0/7.
#
# * Direct circulation "boost" abstraction:
#     0x6773 R/W is verified, but the physical 0->7 forcing effect from an
#     actually OFF baseline is still an open test.
