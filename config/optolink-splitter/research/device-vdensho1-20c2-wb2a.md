# Device / controller / GFA: VDensHO1 20C2 on Vitodens 200-W WB2A

## Identity

Measured read-only over Optolink:

| Address | Raw | Interpretation |
| --- | --- | --- |
| `0x00F8` | `20c2` (first two bytes) | VDensHO1 device ID |
| `0x00F9` | `c2` | controller identification byte |
| `0x00FB` | `03000001` | software-index area; field encoding still unresolved |
| `0x7650` | `2002061501ff` | GFA / combustion-controller chip identification |
| `0x8853` | `02` | modulating burner |

The exact sub-field encoding of `0x7650 = 20 02 06 15 01 ff` is not yet known.

## 0x55D3 runtime block

A read of eleven bytes from `0x55D3` exposes several useful live values in one Optolink transaction:

```bash
/usr/local/bin/optolink-debug request "r;0x55D3;11;raw;False"
```

Hardware-verified on this appliance:

- byte 5, mask `0x20`: flame present
- byte 5, mask `0x40`: GFA lockout

Observed but not yet semantically identified:

- bytes 6..7 form a stable big-endian 16-bit runtime word. Values seen include
  `0x0000`, `0x0820` (2080), `0x0F50` (3920), `0x0B60` (2912) and
  `0x0B62` (2914).
- An earlier hypothesis identified this word as blower rpm because the values
  looked plausible. The 2026-09-22 high-resolution start log contradicts that:
  the word remains approximately 2914 while the verified modulation falls from
  66 % to 33 %. It must therefore remain **unresolved** until an independent
  datapoint or physical measurement confirms its meaning.
- byte 10 / address `0x55DD`: status patterns observed as `01`, `09`,
  `29`, `21`; individual bits are not yet fully decoded.

### 0x55DC modulation

Byte 9 / address `0x55DC` is now hardware-correlated with Vitosoft's
`0xA305` Modulationsgrad:

- `55DC=66` corresponds to `A305 raw=132 -> 66.0 %`
- `55DC=60` corresponds to `A305 raw=120 -> 60.0 %`
- `55DC=50` corresponds to `A305 raw=100 -> 50.0 %`
- `55DC=33` corresponds to `A305 raw=66 -> 33.0 %`

Across the 2026-09-22 single-session run, the two values track essentially
1:1. Small transient differences of one or two percentage points occur because
the two Optolink reads are sequential and typically about 0.12-0.30 s apart.

Conclusion: `0x55DC` is a directly usable live modulation percentage on this
controller. `0xA305` carries the same quantity with raw scale `0.5 %/LSB`.

## 0xA305 modulation datapoint

Vitosoft identifies `0xA305` as `nvoBoilerState_BLR_value / Modulationsgrad`.

The scale factor is hardware-verified as:

```text
percentage = raw_byte * 0.5
```

The 2026-09-22 single-session measurement proved that this percentage tracks
`0x55DC` almost exactly throughout the full startup ramp. This resolves the
previous uncertainty about whether `0x55DC` and `0xA305` represented
different control layers: for this controller they expose the same live
modulation quantity in different encodings.

The single-session logger reads `0x55D3` and `0xA305` sequentially inside
the same TCP connection:

```text
config/optolink-splitter/wb2a-single-session-logger.py
```

## Measured burner-start behavior

Representative single-session high-resolution start on 2026-09-22:

```text
before flame: 55DD 01 -> 09
T= 0.00 s  55DC=66  A305= 0 %  55DD=29
T= 0.55 s  55DC=66  A305=66 %  55DD=29
T= 1.02 s  55DC=66  A305=66 %  55DD=21
...
T=12.56 s  55DC=66  A305=66 %
T=13.12 s  55DC=65  A305=65 %   <- sustained ramp begins
...
T=25.63 s  55DC=50  A305=50 %
...
T=44.70 s  55DC=33  A305=34 %
T=45.17 s  55DC=33  A305=33 %
```

Observed phases:

1. `0x55DD` changes `01 -> 09 -> 29 -> 21` around ignition/flame establishment.
2. From first normal `0x21` state at about T=1.02 s, modulation remains at
   66 % until the sustained fall begins at T=13.12 s: about **12.1 s**.
3. `A305` then falls from 65 % at T=13.12 s to 33 % at T=45.17 s:
   32 percentage points in 32.05 s, essentially **1 percentage point/s**.
4. Modulation then remains at 33 % if the hydraulic system can absorb the heat.

The roughly 12 s regulation delay and approximately 1 %/s ramp-rate limit are
not yet mapped to a specific controller/GFA parameter.

## Pump / hydraulic correlation

Observed internal-pump raw values include:

```text
0132 -> second byte 0x32 = 50
0164 -> second byte 0x64 = 100
```

In captured starts, the lower pump condition correlated with a burner stop before reaching the low-modulation region, while the higher pump condition allowed the burner to reach the floor and continue running.

This is a strong correlation, not proof of causality.

## Open device/GFA questions

1. Decode the fields in `0x7650 = 2002061501ff`.
2. Identify the exact meaning of the `0x55D3` bytes 6..7 runtime word; the
   earlier blower-rpm interpretation is no longer supported.
3. Identify the source of the approximately 12 s post-flame regulation delay.
4. Identify the source of the approximately 1 percentage-point/s downward ramp.
5. Decode all relevant `0x55DD` status bits.
6. Find an independently documented/verified blower-speed datapoint for this
   exact VDensHO1/20C2 generation.


## Candidate origin of the 12 s delay and 1 %/s ramp

### Regulation delay after burner start

Vitosoft contains a dedicated fire-control/timing parameter named:

```text
Reglerverzögerung nach Brennerstart
GWG_FA_Takt_ReglerverzoegerungStart
```

In the LGM29/GWG datapoint families it is part of the `Taktschutz` group and
is associated with the `0x0083` parameter structure. Some LGM29 variants also
use that same structure for burner-minimum-run-time data, so `0x0083` must
not yet be treated as a proven direct byte mapping on this VDensHO1.

Independent Viessmann service documentation for other controller generations
uses parameter `1B` for:

```text
Zeit vom Zünden des Brenners bis zum Beginn der Regelung
```

with the value expressed in seconds and factory setting dependent on the
coding plug.

This semantic definition matches the measured WB2A behavior extremely well:

```text
first normal 0x21 flame state: about T=1.02 s
sustained modulation decrease: about T=13.12 s
difference: about 12.1 s
```

**Current assessment:** the measured ~12.1 s is very likely a deliberate
regulation-delay parameter or equivalent firmware constant. Its exact storage
location on VDensHO1/20C2 is not yet proven.

### Downward modulation ramp

Viessmann controllers with conventional modulating-burner configuration expose
a parameter named:

```text
Laufzeit Stellantrieb Brenner
```

(commonly coding parameter `15`), expressed as the time for actuator travel
and factory-defined according to the coding plug.

The WB2A measurement gives:

```text
65 % -> 33 %
32 percentage points in 32.05 s
=> 0.998 percentage points/s
```

A full 0..100 % actuator travel time of 100 s would mathematically produce:

```text
100 percentage points / 100 s = 1 percentage point/s
```

which matches the observed ramp almost exactly.

The coding-plug raw block also contains an unresolved byte value `0x64 = 100`
at offset `0x1038`:

```text
0x1030 = 41 be 1d e2 03 fc 51 ae 64 9b 00 ff 00 ff 00 ff
                                      ^^
                                     100
```

Vitosoft currently provides no `GWG38` or other semantic label tying this
specific byte to actuator travel time. Therefore this is an **interesting
correlation, not a proven mapping**.

### Candidate read-only locations to test

Two parameter families deserve read-only probing:

- controller-side conventional coding block around `0x5715..`:
  `15` actuator run time, `1A` startup optimization,
  `1B` regulation delay, `1C` burner start delay in other Viessmann
  controller generations;
- LGM29/GWG fire-control timing structure around `0x0083`, where Vitosoft
  lists `Reglerverzögerung nach Brennerstart` for GWG/LGM29 families.

The VDensHO1-specific datapoint list does **not** expose those names directly,
so any result from these addresses must be treated as an experimental
read-only probe rather than an established VDensHO1 mapping.
