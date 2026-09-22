# vcontrold -> Optolink-Splitter mapping

This mapping was derived from the supplied vcontrold/vito configuration for device **20CB / VScotHO1** and the MQTT entities currently used in Home Assistant.

| Legacy vcontrol command | New MQTT topic | Address | Len | Unit |
|---|---|---:|---:|---|
| `getBetriebArtM1` | `openv/heizkreis_m1_betriebsart` | `0x2323` | 1 | `BA` |
| `getBrennerStarts` | `openv/brenner_starts` | `0x088A` | 4 | `CO` |
| `getBrennerStatus` | `openv/brenner_modulation` | `0x55D3` | 1 | `PR1` |
| `getBrennerStunden1` | `openv/brenner_betriebsstunden_1` | `0x08A7` | 4 | `CS` |
| `getBrennerStunden2` | `openv/brenner_betriebsstunden_2` | `0x08AB` | 4 | `CS` |
| `getDrehzahlReduziertA1M1` | `openv/heizkreis_m1_pumpe_reduziert_drehzahl` | `0x27E9` | 1 | `PR1` |
| `getEinflussExtAnforderung` | `openv/externe_anforderung_pumpeneinfluss` | `0x5734` | 1 | `ST` |
| `getEinflussExtSperren` | `openv/externe_sperre_pumpeneinfluss` | `0x5732` | 1 | `ST` |
| `getError0`..`getError9` | `openv/fehlerhistorie_1`..`10` | `0x7507`..`0x7558` | 9 | `ES` |
| `getExtAnforderung` | `openv/externe_anforderung_aktiv` | `0x0A80` | 1 | `RT` |
| `getExtSperren` | `openv/externe_sperre_aktiv` | `0x0A81` | 1 | `RT` |
| `getKA3_KonfiFrostgrenzeM1_GWG` | `openv/heizkreis_m1_frostgrenze_a3` | `0x27A3` | 1 | `UTI` |
| `getKA5` | `openv/heizkreis_m1_pumpenlogik_a5` | `0x27A5` | 1 | `UTI` |
| `getKA6` | `openv/heizkreis_m1_sommersparabschaltung_a6` | `0x27A6` | 1 | `UTI` |
| `getKonfiWirkung_aufPumpe` | `openv/mischer_m2_einfluss_interne_pumpe` | `0x37A8` | 1 | `ST` |
| `getLeistungIst` | `openv/anlagenleistung` | `0xA38F` | 2 | `PR3` |
| `getMaxDrehzahlA1M1` | `openv/heizkreis_m1_pumpe_max_drehzahl` | `0x27E6` | 1 | `PR1` |
| `getMinDrehzahlA1M1` | `openv/heizkreis_m1_pumpe_min_drehzahl` | `0x27E7` | 1 | `PR1` |
| `getNeigungM1` | `openv/heizkreis_m1_heizkennlinie_neigung` | `0x27D3` | 1 | `UN` |
| `getNiveauM1` | `openv/heizkreis_m1_heizkennlinie_niveau` | `0x27D4` | 1 | `ST` |
| `getPumpeDrehzahlIntern` | `openv/interne_pumpe_drehzahl` | `0x7660` | 2 | `PR2` |
| `getPumpeStatusIntern` | `openv/interne_pumpe_status` | `0x7660` | 1 | `RT` |
| `getPumpeStatusM1` | `openv/heizkreis_m1_pumpe_drehzahl` | `0x7663` | 2 | `PR2` |
| `getPumpeStatusZirku` | `openv/zirkulationspumpe_status` | `0x6515` | 1 | `RT` |
| `getSollDrehzahlNebenbetriebA1M1` | `openv/heizkreis_m1_pumpe_nebenbetrieb_drehzahl` | `0x27E8` | 1 | `PR1` |
| `getStatusFrostM1` | `openv/heizkreis_m1_frostschutz_status` | `0x2500` | 1 | `ST` |
| `getStatusStoerung` | `openv/sammelstoerung` | `0x0A82` | 1 | `RT` |
| `getSystemTime` | `openv/systemzeit` | `0x088E` | 8 | `TI` |
| `getTempA` | `openv/aussentemperatur` | `0x0800` | 2 | `UT` |
| `getTempAbgas` | `openv/abgastemperatur` | `0x0808` | 2 | `UT` |
| `getTempAged` | `openv/aussentemperatur_gedaempft` | `0x5527` | 2 | `UT` |
| `getTempKOffset` | `openv/kessel_offset_ueber_warmwasser_soll` | `0x6760` | 1 | `UTI` |
| `getTempKist` | `openv/kessel_isttemperatur` | `0x0802` | 2 | `UT` |
| `getTempKsoll` | `openv/kessel_solltemperatur` | `0x555A` | 2 | `UT` |
| `getTempMaxVorlauf` | `openv/legacy_max_vorlauftemperatur_m1` | `0x2306` | 1 | `UT` |
| `getTempPartyM1` | `openv/heizkreis_m1_party_solltemperatur` | `0x2308` | 1 | `ST` |
| `getTempRL17A` | `openv/legacy_ruecklauftemperatur_17a` | `0x0808` | 2 | `UT` |
| `getTempRaumNorSollM1` | `openv/heizkreis_m1_raumsolltemperatur_normal` | `0x2306` | 1 | `UTI` |
| `getTempRaumRedSollM1` | `openv/heizkreis_m1_raumsolltemperatur_reduziert` | `0x2307` | 1 | `UTI` |
| `getTempVListM1` | `openv/heizkreis_m1_vorlauftemperatur` | `0x2900` | 2 | `UT` |
| `getTempVLsollM1` | `openv/heizkreis_m1_vorlaufsolltemperatur` | `0x2544` | 2 | `UT` |
| `getTempWWist` | `openv/warmwasser_isttemperatur` | `0x0804` | 2 | `UT` |
| `getTempWWsoll` | `openv/warmwasser_solltemperatur` | `0x6300` | 1 | `UTI` |
| `getTimerM1Mo`..`getTimerM1So` | `openv/heizkreis_m1_zeitprogramm_<wochentag>` | `0x2000`..`0x2030` | 8 | `CT` |
| `getUmschaltventil` | `openv/umschaltventil_stellung` | `0x0A10` | 1 | `USV` |

## Source conflicts intentionally retained as legacy topics

- `getTempRL17A` resolves to `0x0808` for device `20CB`, the same address as `getTempAbgas` in the supplied source.
- `getTempMaxVorlauf` uses `0x2306`, which is also used by `getTempRaumNorSollM1` with a different unit/scale in the supplied source.


## VDensHO1 / 20C2 Party control

The live Home Assistant Party switch does **not** use `0x2303=1` for activation.
On VDensHO1 / device 20C2 / SW03, remote `0x2303=1` can be ACKed and then
immediately discarded after Party has been switched off at the physical control
panel. Remote `0x2303=0` remains useful for switching native Party off.

Production therefore uses the persistent `optolink-party-emulator` service:

- store the current operating mode `0x2323` and normal room setpoint `0x2306`;
- mirror Party setpoint `0x2308` to `0x2306`;
- set `0x2323=4` (Dauernd Normal);
- restore the stored mode and normal setpoint on Party OFF;
- apply the configured `0x27F2` Party time limit;
- keep native physical Party detection through `0x2303`.

MQTT interface:

- command: `openv/party_emulation/set` with payload `1` / `0`;
- state: `openv/party_emulation/state`;
- diagnostics: `openv/party_emulation/status`.
