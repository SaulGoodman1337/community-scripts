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
- bytes 6..7, big-endian: blower speed in rpm

Observed values:

- idle: `0x0000` -> 0 rpm
- pre-purge: around `0x0820` -> 2080 rpm
- firing: around `0x0B60` -> 2912 rpm

Additional observed bytes:

- byte 9 / address `0x55DC`: follows a repeatable startup/ramp value around 65/66 down to 33
- byte 10 / address `0x55DD`: status patterns observed as `01`, `09`, `29`, `21`

The individual semantics of `0x55DC` and all bits in `0x55DD` are still under investigation.

## 0xA305 modulation datapoint

Vitosoft identifies `0xA305` as `nvoBoilerState_BLR_value / Modulationsgrad`.

Existing hardware verification in this project uses a scale factor of 0.5:

```text
percentage = raw_byte * 0.5
```

Examples from prior burner-cycle testing:

- raw value corresponding to 66.0 %
- later 61.0 %
- later 55.0 %
- burner off -> 0.0 %

A new single-session logger now reads `0x55D3` and `0xA305` sequentially inside the same TCP connection so both values can be correlated without opening a second Optolink-Splitter TCP client:

```text
config/optolink-splitter/wb2a-single-session-logger.py
```

## Measured burner-start behavior

Representative high-resolution start:

```text
T= 0.00 s  value55DC=65
T= 1.69 s  value55DC=66
T= 3.16 s  value55DC=66
T= 4.85 s  value55DC=66
T= 6.28 s  value55DC=66
T= 7.88 s  value55DC=66
T= 9.43 s  value55DC=66
T=11.02 s  value55DC=66
T=12.48 s  value55DC=65
T=14.21 s  value55DC=64
T=15.56 s  value55DC=62
T=17.26 s  value55DC=60
...
T=45.40 s  value55DC=33
```

Observed phases:

1. stable flame
2. roughly 11-12 s near 65/66
3. controlled ramp downward
4. 65 -> 33 in roughly 33 s, approximately 1 value-point/s
5. stable floor around 33 if heat removal is sufficient

The approximately 11-12 s delay and the ramp-rate limit are not yet mapped to a specific controller/GFA parameter.

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
2. Correlate live `0xA305` with `0x55DC` in the same TCP session.
3. Identify the source of the approximately 11-12 s post-flame regulation delay.
4. Identify the source of the approximately 1 value-point/s downward ramp.
5. Decode all relevant `0x55DD` status bits.
