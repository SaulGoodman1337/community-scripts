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


## Read-only candidate probe result (2026-09-22 20:10)

The single-session logger probed several addresses whose semantics are known
from other Viessmann controller/GFA families:

```text
0x5715 -> 3;0x5715;01
0x571A -> 3;0x571a;01
0x571B -> 3;0x571b;01
0x571C -> 3;0x571c;01
0x0083 -> 3;0x83;01
0x1038 -> 3;0x1038;01
```

On this VDensHO1/20C2 all of these direct reads are rejected by P300
(retcode 3, payload 01).

Consequences:

1. The conventional-controller addresses `0x5715/1A/1B/1C` cannot be reused
   directly on this controller generation.
2. The LGM29/GWG-family `0x0083` timing structure is likewise not exposed at
   that direct address here.
3. Most importantly, `0x1038` is rejected even though byte offset 8 of a
   valid `read;0x1030;16` block is `0x64`. This proves that the coding-plug
   blocks must not be treated as a flat independently addressable byte range.
   A valid base object can return an internal structure whose member bytes are
   not individually readable as P300 addresses.
4. Therefore earlier notation such as "0x1073 = GWG73" should be understood as
   **byte offset 3 inside the 0x1070 coding-plug object**, unless an independent
   direct-address read proves otherwise.

The measured ~12.1 s delay and ~1 %/s ramp correlations remain valid, but their
storage locations are still unknown.


## RKR power path: 0x555C and 0x55E0

Read-only probing on 2026-09-22 confirmed that two datapoints known from other
Viessmann RKR families are directly readable on this VDensHO1/20C2:

```text
read;0x555C;1 -> success
read;0x55E0;1 -> success
```

Vitosoft names these datapoints:

```text
0x555C  RKR_12PSolleff_Kessel   Kesselsollleistung (effektiv)
0x55E0  RKR_04PIst_Kessel      Brennerleistung
```

The same values can be captured without extra transactions by extending two
already useful structures:

```text
read;0x555A;4
  bytes 0..1 = 0x555A Kesselsolltemperatur (effektiv), little-endian / 10
  byte 2     = 0x555C Kesselsollleistung (effektiv)
  byte 3     = 0x555D unresolved

read;0x55D3;14
  byte 9     = 0x55DC live Modulationsgrad
  byte 10    = 0x55DD status
  byte 13    = 0x55E0 Brennerleistung
```

Example while the burner was off:

```text
0x555C = 00
0x55E0 = 01
0x555A;4 = 3d010000
```

`0x013d = 317` confirms the already-used 0.1 C scale for the effective boiler
temperature setpoint, giving 31.7 C in this sample.

The unit/scaling and off-state behavior of `0x55E0` still need dynamic
correlation. The value `01` while off means it should not yet be assumed to
be a literal percentage.

### Why this matters

The next full startup log will distinguish two architectures:

1. `0x555C` drops quickly to a low target while `0x55E0/0x55DC` ramp down
   slowly -> the approximately 1 %/s limitation is downstream in the
   burner/GFA/actuator path.

2. `0x555C` itself ramps down at approximately 1 %/s and the burner follows
   it -> the ramp is already generated by the boiler controller/RKR.

The single-session logger was updated to use exactly two fast block reads
(`0x55D3;14` and `0x555A;4`) so this comparison does not reduce sampling
resolution relative to the previous two-read logger.


## Correction: 0x555C / 0x55E0 are not usable as power values on VDensHO1/20C2

A full high-resolution burner start on 2026-09-22 showed:

```text
0x555C raw = 0 for the entire run
0x55E0 raw = 1 for the entire run
```

while verified live modulation at `0x55DC` changed from about 66 % down to
33 %. Therefore the Vitosoft labels known from other controller families:

```text
0x555C  RKR_12PSolleff_Kessel  Kesselsollleistung (effektiv)
0x55E0  RKR_04PIst_Kessel     Brennerleistung
```

must **not** be transferred to this VDensHO1/20C2 as working power datapoints
just because the addresses are readable.

The VDensHO1-specific Vitosoft datapoint list itself contains `0x555A`
(Kesselsolltemperatur) but does not list either `0x555C` or `0x55E0`.
This device-specific list takes precedence over cross-family address matches.

Conclusion:

- `0x555C`: readable raw byte, semantics unresolved on 20C2
- `0x55E0`: readable raw byte, semantics unresolved on 20C2
- neither value should currently be labelled set power / burner power for this device

The search for the source of the ~1 %/s ramp therefore moves to the CFDM
objects (`0xA380` / `0xA38F`), which have already shown dynamic behavior in
earlier WB2A logs.


## 2026-09-22 high-resolution run: pre-ignition and ramp details

The 20:19 run added several useful observations:

- `0x55DC` starts changing **before flame is present**:
  roughly 30 -> 34 -> 57 -> 67/68 -> 65 while `FL=0`.
- At flame start, `0x55DC` is already about 65 %.
- After flame start it holds about 66 % for roughly 12 s.
- The sustained downward ramp then reaches 33 % after about 44-45 s from
  flame start, again consistent with approximately 1 percentage point/s.
- After flame loss, `0x55DC` remains nonzero briefly (33 -> 30 -> 0),
  confirming that it is a controller modulation command/state value rather
  than a direct proof of instantaneous combustion output.

This makes it even more important to distinguish the controller modulation
command from a downstream actual-power signal.

## CFDM next-step hypothesis

Cross-family Vitosoft metadata identifies:

```text
0xA380  nviProdCmd_CFDM_state/value   Anlagen-/ Kessel-Sollleistung
0xA38F  nvoPWRState_CFDM_state/value Anlagen-Istleistung
```

These names are not present in the VDensHO1-specific datapoint list, so they
remain cross-family hints rather than verified 20C2 semantics.

Earlier hardware logs nevertheless show dynamic `A38F` data. One notable
sample had:

```text
A305 raw = 0x84 -> 66.0 %
A38F raw = 82 01
```

If `A38F` byte 0 uses the same 0.5 %/LSB scaling, `0x82 = 130 -> 65.0 %`,
which is a strong numerical correlation. Byte 1 may be a state/status field,
but that layout is not yet proven.

The single-session logger now records raw `0xA380;2` and `0xA38F;2`
alongside verified `0x55DC` modulation. The goal is to determine whether the
CFDM command changes abruptly while CFDM actual power follows the 1 %/s ramp,
or whether the CFDM command itself is already ramp-limited.


## 2026-09-22 CFDM correlation: 0x55DC command vs 0xA38F active power state

A full single-session start log with simultaneous raw reads of `0x55D3`,
`0xA380` and `0xA38F` resolves an important architectural question.

### Pre-ignition behavior

Before flame is present, `0x55DC` already moves through the startup sequence:

```text
55DC: 30 -> 33 -> 58 -> 67 -> 68 -> 67 -> 66 -> 65 %
FL:   0
A38F: 0000
```

This proves that `0x55DC` is not a direct measurement of current combustion
output. It is better interpreted as the live burner modulation command/state
used by the controller.

At flame establishment:

```text
T=0.00 s  55DC=65  A38F=0000  55DD=29
T=0.74 s  55DC=66  A38F=0000  55DD=21
T=1.48 s  55DC=66  A38F=8201  55DD=21
```

Thus the CFDM power-state object becomes active only after stable flame.

### 0xA38F raw layout

The observed raw form is strongly consistent with:

```text
byte 0 = power/modulation value with 0.5 % per LSB
byte 1 = state/valid flag
```

Examples:

```text
A38F=8201 -> byte0 0x82 = 130 -> 65.0 %
A38F=7c01 -> 124 -> 62.0 %
A38F=6401 -> 100 -> 50.0 %
A38F=5401 ->  84 -> 42.0 %
A38F=4201 ->  66 -> 33.0 %
A38F=0000 -> inactive/off
```

This byte order/scaling is empirically very strong, although the Vitosoft
metadata only names the object as `nvoPWRState_CFDM_state/value` and does
not document the raw member layout.

The second byte changes from 0 to 1 when the active power state becomes valid
after flame establishment and remains 1 during firing.

### Ramp correlation

Across the falling-ramp interval, comparing:

```text
x = 0x55DC modulation command
y = A38F byte0 * 0.5
```

gives approximately:

```text
y = 1.002 * x - 0.04
correlation r ~= 0.996
```

The remaining differences are consistent with:

- sequential sampling delay between the two Optolink reads, and
- coarser update/quantization of the A38F power-state value.

Therefore the approximately 1 percentage-point/s downward ramp is already
present in `0x55DC` before the downstream active-power state follows it.

**Conclusion:** the measured ramp is not explained by a slow physical burner
actuator that receives an immediate lower target. It is generated in the
controller/GFA modulation-command path itself.

This substantially weakens the earlier hypothesis that a generic
"100 s actuator travel time" parameter is the direct cause of the observed
1 %/s ramp.

### 0xA380 result

`0xA380` remained exactly:

```text
00ff
```

for the complete off/start/ramp/steady interval.

The cross-family Vitosoft name is
`nviProdCmd_CFDM_state/value / Anlagen-/Kessel-Sollleistung`, but this object
is evidently not carrying a changing power command in this VDensHO1 heating
mode. A plausible interpretation is that no direct CFDM power command is
active and the boiler instead operates from a temperature demand/local burner
controller. The exact meaning of `00ff` is not yet decoded.

For high-resolution follow-up logging, `0xA380` no longer needs to be sampled
continuously unless a different operating mode is being investigated.
