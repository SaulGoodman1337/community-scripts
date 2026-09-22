# Vitodens 200-W WB2A / VDensHO1 Optolink reverse engineering

> Status: work in progress. Measurements in this document were taken read-only over Optolink on 2026-09-22.  
> Target system identified over Optolink as **VDensHO1 / device ID 20C2** with coding plug **7833971 / 2015:0201**.
>
> This page deliberately separates **measured facts**, **Vitosoft labels**, and **working hypotheses**. Do not treat unresolved raw values as safe write targets. Coding-plug and combustion-controller parameters can affect burner and safety behavior.

## Reference sources

The parameter names below are primarily cross-checked against the Vitosoft-derived datapoint lists from:

- [MorrisonHB/Optolink_02](https://github.com/MorrisonHB/Optolink_02)
- [DP_VScotHO1_20_20251101_190112.txt](https://github.com/MorrisonHB/Optolink_02/blob/master/Optolink_02/Documentation/DP_VScotHO1_20_20251101_190112.txt)
- OpenV/vcontrold device definitions where applicable
- Viessmann WB2A service documentation for the existence of the coding-plug diagnostic data

## Identified device and coding plug

Read-only Optolink queries:

```bash
/usr/local/bin/optolink-debug request "r;0x00F8;2;raw;False"
/usr/local/bin/optolink-debug request "r;0x1010;7;raw;False"
/usr/local/bin/optolink-debug request "r;0x7656;4;raw;False"
/usr/local/bin/optolink-debug request "r;0x7650;6;raw;False"
/usr/local/bin/optolink-debug request "r;0x00F9;1;raw;False"
/usr/local/bin/optolink-debug request "r;0x00FB;4;raw;False"
```

Measured responses:

| Address | Raw | Interpretation | Confidence |
| --- | --- | --- | --- |
| `0x00F8` | `20c2` | device ID: VDensHO1 | high |
| `0x00F9` | `c2` | controller identification byte | high; exact semantics not yet decoded |
| `0x00FB` | `03000001` | software-index area | high that this is the Vitosoft software-index datapoint; field encoding unresolved |
| `0x1010` | `37383333393731` | ASCII `7833971`, coding-plug part number | high |
| `0x7656` | `20150201` | coding-card type/revisions; displayed as `2015:0201` | high |
| `0x7650` | `2002061501ff` | GFA / combustion-controller chip identification | high that this is the GFA ID; byte-field meaning unresolved |

The `0x1010` payload decodes directly as ASCII:

```text
37 38 33 33 39 37 31
 7  8  3  3  9  7  1

=> 7833971
```

## Coding-plug parameter blocks

The regulator exposes coding-plug data in the `0x10xx` range.

Measured raw blocks:

```text
0x1030  41be1de203fc51ae649b00ff00ff00ff
0x1040  0215000000000000
0x1050  00000002000000004a143f0a41410000
0x1060  04081e0405041e140000000000000000
0x1070  051d141841323c000000000000000000
0x1080  04081e28370003080000000000000000
0x1090  002121212f373f48515a640000000000
```

### GWG60-GWG67

Vitosoft labels the `0x1060` structure as:

| GWG | Vitosoft label | Measured raw byte |
| --- | --- | ---: |
| GWG60 | Einschaltdifferenz | 4 |
| GWG61 | Ausschaltdifferenz | 8 |
| GWG62 | Reglerverstärkung KT-Regler | 30 |
| GWG63 | Reglernachstellzeit KT-Regler | 4 |
| GWG64 | Ausschaltdifferenz Brenner bei Volllast | 5 |
| GWG65 | Brennermindestpausenzeit | 4 |
| GWG66 | Differenztemperatur zum Abbruch der Brennermindestpausenzeit | 30 |
| GWG67 | Temperatur zum Abbruch der Brennermindestpausenzeit | 20 |

The scale/unit for GWG62-GWG67 is not yet proven on this WB2A.

**GWG61 = 8 is experimentally supported.** During one long burner run the boiler shut down at approximately:

```text
Kessel-Ist  = 58.0 C
Kessel-Soll = 50.0 C
difference  = +8.0 K
```

This matches the measured coding-plug value `GWG61 = 8`.

### GWG70-GWG76

Measured:

```text
0x1070 = 05 1d 14 18 41 32 3c ...
```

Vitosoft mapping:

| GWG | Vitosoft label | Raw |
| --- | --- | ---: |
| GWG70 | Minimale Kesseltemperatur | 5 |
| GWG71 | Brennerminimalleistung | 29 |
| GWG72 | Offset modulierender Brenner | 20 |
| GWG73 | Anfahroptimierung modulierender Brenner | 24 |
| GWG74 | Kesselsollleistung im Speicherbetrieb | 65 |
| GWG75 | Mindestdrehzahl interne Pumpe | 50 |
| GWG76 | Nachlaufzeit interne Pumpe | 60 |

Important corrections:

- **GWG71 = 29 must not currently be equated directly with the observed modulation floor.** The directly observed modulation floor is 33 and the burner-characteristic table below explains why.
- **GWG73 = 24 is not a simple "hold startup power for 24 seconds" timer.** A high-resolution start measurement disproves that interpretation.

## Burner characteristic GWG91-GWG9A

This is currently the strongest result.

Vitosoft labels:

```text
GWG91  Modulationsgrad bei 10 % Leistung
GWG92  Modulationsgrad bei 20 % Leistung
GWG93  Modulationsgrad bei 30 % Leistung
GWG94  Modulationsgrad bei 40 % Leistung
GWG95  Modulationsgrad bei 50 % Leistung
GWG96  Modulationsgrad bei 60 % Leistung
GWG97  Modulationsgrad bei 70 % Leistung
GWG98  Modulationsgrad bei 80 % Leistung
GWG99  Modulationsgrad bei 90 % Leistung
GWG9A  Modulationsgrad bei 100 % Leistung
```

Measured block:

```text
0x1090 = 00 21 21 21 2f 37 3f 48 51 5a 64 00 00 00 00 00
```

Therefore the measured characteristic is:

| Requested burner output | Modulation value |
| ---: | ---: |
| 10 % | 33 |
| 20 % | 33 |
| 30 % | 33 |
| 40 % | 47 |
| 50 % | 55 |
| 60 % | 63 |
| 70 % | 72 |
| 80 % | 81 |
| 90 % | 90 |
| 100 % | 100 |

Consequences:

1. The practical modulation floor in this characteristic is **33**.
2. A live modulation value around **65-66** lies between the 60 % and 70 % characteristic points.
3. Linear interpolation gives approximately:

```text
MOD 65 -> about 62.2 % requested burner output
MOD 66 -> about 63.3 % requested burner output
```

This validates the original observation that the WB2A starts at roughly **60-65 % burner output**.

An earlier working hypothesis that modulation value 65/66 represented 100 % output was therefore wrong and has been discarded.

## Live burner/status datapoints

### 0x55D3..0x55DD block

Reading eleven bytes from `0x55D3` proved useful because the last two bytes expose the startup sequence clearly:

```bash
/usr/local/bin/optolink-debug request "r;0x55D3;11;raw;False"
```

Observed:

- `0x55DC`: live burner modulation value
- `0x55DD`: burner/flame status bit field

Observed status values:

| 0x55DD | Observed state |
| --- | --- |
| `0x01` | burner off / no stable flame |
| `0x09` | ignition/start sequence |
| `0x29` | transition into stable flame |
| `0x21` | stable normal burner operation |

These are observational labels. The individual bits are not yet fully decoded.

### 0xA305

Vitosoft identifies `0xA305` as:

```text
nvoBoilerState_BLR_value
Modulationsgrad
```

A read while the burner was off returned:

```text
0xA305 = 00
```

This is consistent with zero modulation but does not yet tell us how `0xA305` relates to `0x55DC` during operation. A simultaneous running-burner measurement is still required.

### Brennertyp

```text
0x8853 = 02
```

Vitosoft's conditions identify value `2` as a **modulating burner**, consistent with the measured behavior.

## Measured burner-start sequence

High-resolution sampling of `0x55D3;11` produced approximately 1.4-1.7 second sample spacing.

Representative start:

```text
T= 0.00 s  MOD=65  STATUS=0x29
T= 1.69 s  MOD=66  STATUS=0x21
T= 3.16 s  MOD=66
T= 4.85 s  MOD=66
T= 6.28 s  MOD=66
T= 7.88 s  MOD=66
T= 9.43 s  MOD=66
T=11.02 s  MOD=66
T=12.48 s  MOD=65
T=14.21 s  MOD=64
T=15.56 s  MOD=62
T=17.26 s  MOD=60
T=20.32 s  MOD=56
T=24.90 s  MOD=51
T=28.00 s  MOD=47
T=32.75 s  MOD=41
T=37.38 s  MOD=38
T=40.56 s  MOD=35
T=43.72 s  MOD=34
T=45.40 s  MOD=33
```

Measured phases:

1. Stable flame appears.
2. Modulation remains at about 65-66 for roughly **11-12 seconds**.
3. A controlled ramp-down starts.
4. Modulation falls from 65 to 33 over about **32.9 seconds**.
5. Average ramp slope is approximately **-0.97 modulation points per second**.
6. The burner can then remain at 33 for an extended period if the hydraulic system can absorb the heat.

This strongly suggests a deliberately rate-limited startup/ramp behavior rather than an immediate jump from startup output to minimum modulation.

### GWG73 finding

Because the actual constant high-modulation phase is only about 11-12 seconds, the measured:

```text
GWG73 = 24
Anfahroptimierung modulierender Brenner
```

cannot simply mean "24 seconds at startup modulation".

Vitosoft data for other Viessmann controller families also contains separate concepts such as **Anfahroptimierung**, **Reglerverzoegerung nach Brennerstart**, and **Startverzoegerung Brenner**. The exact equivalent parameter location for this WB2A/GFA has not yet been identified.

## Pump correlation

Observed pump data contained:

```text
0132 -> second byte 0x32 = 50
0164 -> second byte 0x64 = 100
```

This is consistent with pump speed values of 50 % and 100 %, and `GWG75 = 50` is labeled by Vitosoft as the minimum internal-pump speed.

In the captured runs:

- with the lower pump value, one burner start terminated before reaching the modulation floor;
- with the higher pump value, another start reached modulation 33 and continued running.

This is a **strong correlation**, not yet proof of causality. It supports the working hypothesis that sufficient heat removal during the approximately 45-second startup/ramp interval is important for avoiding early cycling.

## 0x1030 block: unresolved structure

Measured:

```text
0x1030 = 41be1de203fc51ae649b00ff00ff00ff
```

Vitosoft associates the `0x1030` structure with, among other fields:

- GWG30: Begrenzung max. Warmwasserleistung
- GWG32: Begrenzung max. Heizleistung
- GWG34: Bauart Umschaltventil

Do **not** currently assume that every GWG number maps to the same simple byte offset here. The raw bytes contain additional values and the exact structure/scaling has not yet been proven.

## Read-only commands used so far

```bash
/usr/local/bin/optolink-debug request "r;0x00F8;2;raw;False"
/usr/local/bin/optolink-debug request "r;0x00F9;1;raw;False"
/usr/local/bin/optolink-debug request "r;0x00FB;4;raw;False"
/usr/local/bin/optolink-debug request "r;0x1010;7;raw;False"
/usr/local/bin/optolink-debug request "r;0x1030;16;raw;False"
/usr/local/bin/optolink-debug request "r;0x1040;8;raw;False"
/usr/local/bin/optolink-debug request "r;0x1050;16;raw;False"
/usr/local/bin/optolink-debug request "r;0x1060;16;raw;False"
/usr/local/bin/optolink-debug request "r;0x1070;16;raw;False"
/usr/local/bin/optolink-debug request "r;0x1080;16;raw;False"
/usr/local/bin/optolink-debug request "r;0x1090;16;raw;False"
/usr/local/bin/optolink-debug request "r;0x55D3;11;raw;False"
/usr/local/bin/optolink-debug request "r;0x7650;6;raw;False"
/usr/local/bin/optolink-debug request "r;0x7656;4;raw;False"
/usr/local/bin/optolink-debug request "r;0x8853;1;raw;False"
/usr/local/bin/optolink-debug request "r;0xA305;1;raw;False"
```

## Open questions

Current priorities:

1. Determine the exact meaning/field layout of GFA ID `2002061501ff`.
2. Measure `0xA305` and `0x55DC` simultaneously while the burner is running.
3. Locate the parameter that produces the approximately 11-12 second delay before the sustained modulation ramp starts.
4. Locate or explain the approximately 1 modulation-point/second downward ramp limit.
5. Determine the exact scaling of GWG62, GWG63, GWG71, GWG72 and GWG73 for this controller generation.
6. Decode `0x1030` without assuming a byte layout.
7. Compare an original second WB2A coding plug offline, if available, to isolate model-specific constants.

## Safety boundary

The current reverse engineering is intentionally **read-only**.

The coding plug and combustion-controller parameter sets include burner, gas/air, ignition, flame-supervision and temperature-limit related data. A raw value being readable over Optolink does not make it a safe or supported write target. Any future write experiment should first prove that a parameter is non-combustion-related and non-safety-critical.
