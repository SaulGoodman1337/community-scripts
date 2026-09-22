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

  Dynamic burner-cycle verification of 0x55D3 bytes 6..7 (big-endian):
    idle:       0x0000 -> 0 rpm, A305=0.0 %, flame=false
    pre-purge:  0x0820 -> 2080 rpm, A305=0.0 %, flame=false
    firing:     0x0B60 -> 2912 rpm, A305=66.0 %, flame=true
    firing:     0x0B62 -> 2914 rpm, A305=61.0/55.0 %, flame=true
    flame off:  0x0000 -> 0 rpm, A305=0.0 %, flame=false
    Result: bytes 6..7 are hardware-verified as blower speed in rpm on this
    WB2A/VDensHO1 controller. Direct reads at 0x55D9 and 0x55DA are rejected
    with P300 retcode 3 / payload 0x01; the value must be extracted from the
    9-byte 0x55D3 block.
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

  Party mode P300 write tests on the real appliance:
    Before local Party initialization/confirmation, write 0x2303 len1 value 1
    was ACKed but reverted to 0 and did not change the effective 0x2500 state.
    This was reproduced both in normal operation and in forced reduced mode.
    Writing the Party setpoint 0x2308 first did not change that behavior.

    After Party had once been fully activated/confirmed at the physical control
    panel, the same raw writes became stable:
      write 0x2303 len1 value 0 -> ACK, read-back remains 0
      write 0x2303 len1 value 1 -> ACK, read-back remains 1
      0x2500 byte 8 follows 0x01 (Party off) <-> 0x02 (Party on)
    Repeated remote OFF/ON tests then worked without touching the control panel.

    A byte-by-byte read-only scan of 0x2300..0x233F while toggling Party at the
    physical control panel found only 0x2303 changing.  0x2330 is not a usable
    command on this exact 20C2/SW03 controller: write 0x2330 returned P300
    retcode 3 / payload 0x01.

    Later testing refined that conclusion: local Party OFF makes subsequent
    remote 0x2303=1 writes fail again. The write is ACKed, then 0x2303 returns
    to 0 and 0x2500 remains in the non-Party state. Writing 0x2308 after 0x2303
    to imitate a temperature confirmation also does not make remote Party ON
    stick. Remote 0x2303=0 remains reliable.

    Production therefore treats 0x2303 as native Party status/off-control, not
    as a dependable remote ON actuator. Synthetic Party uses the separately
    hardware-verified path 0x2323=4 (Dauernd Normal), stores/restores the prior
    0x2323 mode and 0x2306 normal setpoint, mirrors 0x2308 into 0x2306 while
    active, and applies the configured 0x27F2 time limit.

    End-to-end synthetic Party validation on the real appliance:
      baseline: 0x2323=2, 0x2306=21 C, 0x2308=21 C
      mode-only test:
        0x2323 2 -> 4 produced program 0x2301=2 and effective 0x2500 party-like
        state byte 8=0x02; restore 4 -> 2 returned program 0x2301=3 and
        0x2500 byte 8=0x01.
      distinct-setpoint test:
        0x2308 changed 21 -> 22 while 0x2306 stayed 21;
        synthetic Party ON produced 0x2306=22 and 0x2323=4;
        synthetic Party OFF restored 0x2306=21 and 0x2323=2.
      native physical Party interoperability:
        physical Party ON produced 0x2303=1 / 0x2500 byte 8=0x02 and the HA
        switch followed ON; physical Party OFF produced 0x2303=0 /
        0x2500 byte 8=0x01 and HA followed OFF.

  Party room setpoint P300 write test on the real appliance:
    initial 0x2308 = 0x15 = 21 C
    write 0x2308 len1 value 22 -> ACK
    read-back 0x16 = 22 C
    0x2500 bytes 12..13 and 20..21 -> 0x00DC = 22.0 C
    restore write value 21 -> ACK
    read-back 0x15 = 21 C
    0x2500 bytes 12..13 and 20..21 -> 0x00D2 = 21.0 C
    Result: 0x2308 is hardware-verified READ/WRITE for the party room
    setpoint on this exact controller.

  Normal/reduced room setpoint P300 write tests:
    0x2306 initial 21 C -> write 22 -> ACK -> read-back 22 -> restore 21
    0x2307 initial 18 C -> write 19 -> ACK -> read-back 19
      current reduced-mode 0x2500 effective setpoint changed 18.0 -> 19.0 C
      restore 18 -> effective setpoint returned to 18.0 C
    Result: 0x2306 and 0x2307 are hardware-verified READ/WRITE.

  Economy mode write probe:
    0x2302 initial/read-back 0
    write 1 -> transport ACK, but read-back immediately remained 0 and
      0x2500 did not change
    write 0 -> ACK, read-back 0
    Result: 0x2302 is hardware-verified READ, but writing it is ineffective
    on this exact 20C2 / SW-index 0x03 controller. Do not expose 0x2302 as
    an HA command topic merely because the P300 write telegram is ACKed.
    Probe of alternate command register 0x2331 len1 returned P300 error
    (retcode 3 / payload 0x01), so 0x2331 is not available as an ordinary
    datapoint on this firmware either.

  Operating-mode P300 write test:
    initial 0x2323 = 0x02 = heating + DHW
    0x2301 = 0x03 = heating + DHW according to timer program
    0x2500 byte 1 = 0x01 = reduced operation at that moment
    write 0x2323 len1 value 4 -> ACK
    read-back 0x2323 = 0x04 = continuous normal
    0x2301 changed to 0x02 = continuous normal heating
    0x2500 byte 1 changed to 0x03 = continuous normal
    effective room setpoint changed to 21.0 C
    restore write 0x2323 value 2 -> ACK/read-back 0x02
    0x2301 returned to 0x03 and 0x2500 byte 1 returned to 0x01
    Result: 0x2323 is hardware-verified READ/WRITE. 0x2301 is a
    hardware-verified read-only operating-mode/status datapoint.

  DHW setpoint P300 write test:
    initial 0x6300 = 0x2D = 45 C
    0x6500 effective DHW setpoint = 45.0 C
    actual DHW temperature 0x0812 = 43.5 C
    write 0x6300 len1 value 44 -> ACK
    read-back 0x2C = 44 C
    0x6500 followed to 44.0 C, DHW charging stayed inactive
    restore write value 45 -> ACK/read-back 0x2D
    0x6500 returned to 45.0 C
    Result: 0x6300 is hardware-verified READ/WRITE.

  Circulation configuration/status snapshot:
    0x6515 = 1 (circulation pump ON)
    0x0842 = 1 (relay K12 ON)
    0x6771 = 0 (circulation at DHW setpoint 1: control function)
    0x6772 = 0 (circulation at DHW setpoint 2: control function)
    0x6773 = 0 (circulation interval mode: timer program)
    0x7753 = 1 (K12 assignment = circulation pump)
    0x0846 len1 -> P300 error retcode 3 / payload 0x01
    Result: on this exact controller K12 is explicitly assigned to the
    circulation pump, and 0x6515 + 0x0842 report the same live ON state.
    The generic/older 0x0846 circulation address is not available as an
    ordinary datapoint on this firmware.

  Circulation interval/config write test:
    initial 0x6773 = 0 (timer program)
    write 0x6773 len1 value 7 -> ACK
    read-back 0x07 = continuous ON
    0x6515 and 0x0842 remained 1 because the pump was already ON at test time
    restore write 0 -> ACK/read-back 0x00
    Result: 0x6773 is hardware-verified READ/WRITE. Physical forcing effect
    of value 7 still needs one test while the pump is initially OFF.

  Circulation timer program readout:
    0x2200/08/10/18/20/28/30 all returned 2B A8 FF FF FF FF FF FF.
    Decoded for Monday through Sunday: 05:30-21:00, one active interval/day.
    At 2026-09-21 20:57 the live state matched the schedule:
      0x6515 = 1, 0x0842 = 1, 0x6773 = 0 (timer mode).
    A follow-up after 21:00 still showed 0x6515 = 1 and 0x0842 = 1 while
    0x6773 remained 0. A 0->7->0 probe again verified 0x6773 read/write,
    but still could not prove the physical forcing effect because the pump
    never reached an OFF baseline.

  Controller clock / schedule-edge test:
    0x088E len8 is readable and writable as DateTimeBCD.
    Original appliance clock: 2026-09-21 20:55:48.
    Write 20:59:00 -> ACK/read-back 20:59:03.
    Write 21:01:00 -> ACK/read-back 21:01:02.
    During 40 s after the direct jump across 21:00, 0x6515 and 0x0842
    remained 1 while 0x6773 remained 0.
    The original clock was restored with elapsed test time added.
    Result: 0x088E R/W is hardware-verified. A direct clock jump over the
    programmed switch-off edge does not cause an immediate schedule
    reevaluation on this controller. Test the edge by setting the clock just
    before 21:00 and letting it cross 21:00 naturally.

  Read-only validation sample:
    0x2900 = 37.3 C (A1/M1 flow temperature)
    0x0810 = 37.3 C (filtered boiler temperature)
    0x0816 = 33.0 C (filtered flue-gas temperature)
    0x5525 = 14.4 C (filtered outdoor temperature)
    0x555A = 5.0 C (effective boiler target)
    0x7660 len2 = 00 00 (internal pump output OFF, speed 0 percent)
    0x7663 len2 = 00 00 (A1 pump output OFF, speed 0 percent)
    0x088A len4 = 61 6F 07 00 = 487265 burner starts, unsigned LE
    0x08A7 len4 = 80 03 CE 03 = 63832960 s = 17731.4 h
    0x0886 len4 = 7E 03 CE 03 = 63832958 s = 17731.4 h
    0xA305 = 0x00 -> 0.0 percent with catalog div2 scaling
    0x55D3 byte5 = 0x01 -> flame false, lockout false
    0x55DD = 0x01 -> flame bit false
    Result: 0x2900, 0x555A, 0x7660, 0x7663 and the burner counters are
    hardware-readable on this exact appliance. 0x088A must be treated as
    unsigned.

  Dynamic burner firing test:
    Flame transition observed in 0x55D3:
      ...000001... -> ...0021... at ignition
    Both flame indicators agreed throughout:
      0x55D3 byte5 mask 0x20 and 0x55DD mask 0x20
    Lockout bit 0x55D3 byte5 mask 0x40 remained false.
    During flame, 0xA305/div2 tracked:
      66.0, 53.0, 36.0, 33.0, 33.0, 33.0, 33.0 percent
    After flame-off, 0xA305 returned immediately to 0.0 percent.
    Result: 0xA305/div2 is hardware-verified burner modulation/load in percent
    on this exact 20C2 / VDensHO1 SW03 appliance.

    Pump behavior during the same firing cycle:
      0x7660 internal pump = status 1, speed 100 percent during firing;
      after flame-off it remained status 1 at 50 percent (pump overrun).
      0x7663 A1 pump = status 1, speed 100 percent during firing;
      after flame-off it changed to status 0, speed 0 percent.
      0x2906 remained 1 in the post-flame samples while 0x7663 was already
      0/0, so 0x2906 should be treated as a logical/requested HC pump state,
      not blindly equated with the physical 0x7663 output.

    Temperature/target evolution during the firing cycle:
      0x0810 boiler temp rose into roughly 41-50 C
      0x555A effective boiler target varied 30.0 -> 19.0 -> 20.9 -> 22.7 C,
      then returned to 5.0 C after flame-off.
      0x0816 filtered flue-gas temperature stayed near 32 C in these samples.

  Coding/topology readout:
    0x7700 len2 = 02 01, i.e. 0x7700=2 (A1 + DHW) and adjacent
    0x7701=1 (single-boiler installation). Use len1 per datapoint in the poll list.
    0x1010 len7 = ASCII "7833971" (boiler coding plug part number).
    0x1040 len2 = 02 15 (coding-plug identifier raw; catalog uses rotatebytes).
    0x7330 = 1 (control-unit software index).
    0x7650 = 0x20 (GFA identifier).

  A1/M1 coding readout:
    A2=2 (storage priority)
    A3=-9 C (frost threshold)
    A4=0 (frost protection active / not blocked)
    A5=5 (summer-save/HPL threshold: outdoor > room target + 1 K)
    A6=5 C (absolute summer-save threshold)
    A7=0 (no mixer economy function)
    A9=7 min (HC pump behavior in reduced operation)
    C5=38 C, C6=50 C
    D3=0.8 heating-curve slope, D4=+5 K heating-curve level
    E5=0 (staged HC pump)
    E6=100 percent max, E7=30 percent min
    E8=0 (minimum according to E7), E9=50 percent reduced speed
    F1=0 (temperature program passive), F2=8 h party time limit
    0x27F8/0x27F9/0x27FA/0x27FB all return P300 error retcode 3 / payload 0x01
    on this exact SW03 controller; do not poll them in normal groups.

  Boiler/DHW coding readout:
    0x5706=81 C boiler maximum
    0x5730=1 internal pump speed-controlled
    0x5731=100 percent internal-pump setting
    0x6760=20 K DHW boiler offset
    0x6762 byte0=5 min DHW loading-pump overrun; exact catalog length is 1
    0x6765=3 Grundfos diverter valve

  Fault-history hardware readout:
    All ten 9-byte slots 0x7507..0x7558 are readable.
    Newest: F9 at 2026-09-21 17:31:44.
    Slots 2..10: recurring B7 entries from 2026-07-09 through 2026-09-19.
    This VDensHO1 encodes weekday as ISO-style Monday=1 .. Sunday=7 in the
    observed history records (and 0x088E Monday=1), unlike the Sunday=0
    convention observed on some other controller families.

  Heating / DHW schedule and state readout:
    A1/M1 heating schedule 0x2000..0x2030:
      Monday through Sunday all 28 A0 FF FF FF FF FF FF = 05:00-20:00.
    DHW schedule 0x2100..0x2130:
      Monday through Sunday all 2B A8 FF FF FF FF FF FF = 05:30-21:00.
    0x2544 = 0.0 C (A1/M1 flow target at sample time, outside heating window)
    0x2900 = 37.6 C (A1/M1 flow actual)
    0x0810 = 37.6 C (filtered boiler temperature)
    0x6513 = 0 (storage loading pump OFF)
    0x650A = 0 (DHW loading inactive)
    0x0A10 = 1 (diverter valve direction heating)
    0x081A = 20.0 C (VTS filtered temperature)
    0x080C = 20.0 C (hydraulic separator temperature)
    Together with the earlier 0x0A10=3 sample during DHW direction, the new
    0x0A10=1 sample confirms the exact enum 1=heating, 3=DHW on hardware.
    Result: schedules, 0x2544, 0x6513, 0x650A and 0x0A10 are hardware-readable
    on this appliance.

  Optional-hardware inventory:
    0x7752 = 0 -> hydraulic separator NOT configured/present.
      Therefore 0x080C = 20.0 C is a default/non-physical value on this system;
      keep it out of productive polling.
    0x7754 = 0 -> no Vitosolic solar controller configured.
    0x656A = 0, 0x6552 = 0 and both 0x6564/0x6566 = 3276.7 C.
      3276.7 C corresponds to raw 0x7FFF with div10 and is an invalid/sentinel
      temperature here. Solar datapoints are not applicable on this system.
    System schema 0x7700 = 2 already identifies A1 + DHW with no M2 circuit.
      M2 probes additionally returned 0x3900=0.0 C, 0x3544=0.0 C,
      0x0898=20.0 C and 0x7665=0000: inactive/default values, not a live M2.
    Sensor-status follow-up:
      0x083A = 0 -> outdoor-temperature sensor OK
      0x083B = 0 -> boiler-temperature sensor OK
      0x083D = 2 -> STS2 open circuit
      0x0840 = 2 -> VLTS/VTS open circuit
      0x089C = 3 -> M1 room-temperature sensor reference error
      0x089D = 3 -> M2 room-temperature sensor reference error
      0x2521 = 2 -> A1/M1 weather-compensated control
      0x3521 = 5 -> M2 heating circuit not present
    Therefore 0x081A=20.0 C is not a physical VTS/VLTS value on this system.
    Likewise 0x0896=20.0 C must not be exposed as a valid room temperature
    while 0x089C reports reference error.

  DHW / coding-plug readout:
    0x8851 = 0 -> DHW construction type "Speicher".
    0x6756 = 0 -> configured DHW setpoint range is 10..60 C.
    0x6759 = 0 -> DHW switch-on threshold is 2.5 K below setpoint.
    0x675B = 0 -> storage tank connected "vor Weiche" (separator itself absent).
    0x6760 = 20 K boiler offset; 0x6762 = 5 min pump overrun.
    0x0812 = 43.3 C is a valid DHW temperature sample.
    0x0814 = 20.0 C while 0x083D = 2 (open circuit), therefore STS2 is not a
    physical temperature source on this installation.

    Coding-plug block 0x1050 len16:
      raw = 00 00 00 02 00 00 00 00 4A 14 3F 0A 41 41 00 00
      byte 0 = 0 -> device-type numeric value GWG50; semantic mapping not
               documented in the VDensHO1 source catalog, so keep it raw only
      byte 1 = 0 -> GWG51 boiler-side DHW type "Umlaufwasserheizer"
      byte 3 = 2 -> GWG53 modulating burner
      byte 8 = 74 C boiler-setpoint hardware maximum
      byte 9 = 20 C boiler-setpoint hardware minimum
      byte10 = 63 C DHW-setpoint coding-plug maximum
      byte11 = 10 C DHW-setpoint coding-plug minimum
      byte12 = 65 percent DHW maximum power
      byte13 = 65 percent heating maximum power
    Important: the currently configured 0x6756=0 restricts DHW operation to
    10..60 C even though the coding plug advertises an absolute 10..63 C
    capability. Use 10..60 C for the Home Assistant number entity unless the
    controller coding is intentionally changed.

    Coding-plug commissioning-date block 0x1020 len16:
      raw = 00 00 FF FF FF 00 00 00 00 00 00 00 00 00 00 00
      byte 2 = day, byte 3 = month, byte 4 = year
      all three are 0xFF on this appliance, so no valid commissioning date is
      programmed in the coding-plug block. Do not expose 255/255/255 as a date.

    Coding-plug configuration block 0x1030 len16:
      raw = 41 BE 1D E2 03 FC 51 AE 64 9B 00 FF 00 FF 00 FF
      byte 0 = 65 percent max DHW power limit (GWG30)
      byte 2 = 29 percent max heating power limit (GWG32)
      byte 4 = 3 = Grundfos diverter valve (GWG34)
      each meaningful even byte in the observed block is followed by its
      bytewise complement (e.g. 0x41/0xBE, 0x1D/0xE2, 0x03/0xFC).
      Bytes 6, 8, 10, 12 and 14 are not exposed because no verified VDensHO1
      semantic mapping for them is present in the source catalog used here.

    Coding-plug regulator block 0x1060 len16:
      raw = 04 08 1E 04 05 04 1E 14 00 00 00 00 00 00 00 00
      byte 0 = 4 K switch-on differential (GWG60)
      byte 1 = 8 K switch-off differential (GWG61)
      byte 2 = 30 / 10 = 3.0 percent/K boiler-temperature controller gain (GWG62)
      byte 3 = 4 * 10 s = 40 s boiler-temperature controller reset time (GWG63)
      byte 4 = 5 K burner switch-off differential at full load (GWG64)
      byte 5 = 4 min burner minimum pause (GWG65)
      byte 6 = 30 K differential threshold for cancelling minimum pause (GWG66)
      byte 7 = 20 C temperature threshold for cancelling minimum pause (GWG67)
    These are coding-plug regulator constants and are exposed read-only.

    Coding-plug block 0x1070 len16:
      raw = 05 1D 14 18 41 32 3C 00 00 00 00 00 00 00 00 00
      byte 0 = 5 C minimum boiler temperature (GWG70)
      byte 1 = 29 percent burner minimum power (GWG71)
      byte 2 = 20 K modulating-burner offset (GWG72)
      byte 3 = 24 * 10 s = 240 s burner startup optimization (GWG73)
      byte 4 = 65 percent boiler target power in storage-tank mode (GWG74)
      byte 5 = 50 percent minimum internal-pump speed (GWG75)
      byte 6 = 60 s internal-pump overrun (GWG76)
    This block is read-only in the productive profile. The 29 percent GWG71
    value is the appliance coding-plug burner minimum; GWG75 is explicitly the
    minimum speed of the internal pump, not the burner blower.

    Coding-plug DHW/DLH regulator block 0x1080 len16:
      raw = 04 08 1E 28 37 00 03 08 00 00 00 00 00 00 00 00
      GWG80 byte 0 = 4 K DLH switch-off differential start/stop
      GWG81 byte 1 = 8 K DLH switch-on differential start/stop
      GWG82 byte 2 = 30 s DLH overrun
      GWG83 byte 3 = 40 s DLH maximum rise time
      GWG84 byte 4 = 55 / 10 = 5.5 percent/K DLH controller gain
      GWG85 byte 5 = 0 * 10 s = 0 s DLH derivative/lead time
      GWG86 byte 6 = 3 * 10 s = 30 s DLH reset time
      GWG87 byte 7 = 8 K DLH switch-off differential
      GWG88 byte 8 = 0 = circulation pump during tank charging: control function
    Source terminology calls GWG80..GWG87 "DLH"; depending on the installed
    DHW design some of these coding-plug constants may be inactive.

    Coding-plug Grundfos diverter-valve block 0x10C0 len16:
      raw = 5A 32 2D C8 5A 32 02 32 02 32 00 FF FF FF FF FF
      GWGC0 byte 0  = 90 steps, travel x1
      GWGC1 byte 1  = 50 frequency value, travel x1
      GWGC2 byte 2  = 45 * 2 = 90 steps, travel x2
      GWGC3 byte 3  = 200 * 2 = 400 frequency value, travel x2
      GWGC4 byte 4  = 90 steps, travel x3
      GWGC5 byte 5  = 50 frequency value, travel x3
      GWGC6 byte 6  = 2 steps, travel x4
      GWGC7 byte 7  = 50 frequency value, travel x4
      GWGC8 byte 8  = 2 steps, travel x5
      GWGC9 byte 9  = 50 frequency value, travel x5
      GWGCA byte 10 = 0, heating position
    GWG34 in block 0x1030 selects Grundfos (3), so 0x10C0 is the applicable
    diverter-valve motion profile for this appliance. The source catalog does
    not specify a physical unit for the frequency values; do not label them Hz.

    Coding-plug burner characteristic block 0x1090 len16:
      raw = 00 21 21 21 2F 37 3F 48 51 5A 64 00 00 00 00 00
      GWG91 / 10 percent requested output  -> 33 percent modulation
      GWG92 / 20 percent requested output  -> 33 percent modulation
      GWG93 / 30 percent requested output  -> 33 percent modulation
      GWG94 / 40 percent requested output  -> 47 percent modulation
      GWG95 / 50 percent requested output  -> 55 percent modulation
      GWG96 / 60 percent requested output  -> 63 percent modulation
      GWG97 / 70 percent requested output  -> 72 percent modulation
      GWG98 / 80 percent requested output  -> 81 percent modulation
      GWG99 / 90 percent requested output  -> 90 percent modulation
      GWG9A / 100 percent requested output -> 100 percent modulation
    The lower 10/20/30 percent points all map to 33 percent modulation. This is
    the coding-plug characteristic curve; do not confuse the curve values with
    the separate GWG71 burner-minimum parameter (29 percent).

  Internal diagnostic readout:
    0x0A33 len1 = 00 -> KM Error PumpeA1 raw status 0
    0x0A35 len1 = 00 -> KM Error PumpeIntern raw status 0
    0x5738 len1 = 00 -> Vitosoft name "(38) aktueller Fehlerstatus GFA", raw 0

    0x778B len4 = 00 01 03 03:
      0x778B = 0  -> EEPROM status
      0x778C = 1  -> control-software version upper byte
      0x778D = 3  -> control-software version lower byte
      resulting displayed control-software version = 1.3
      0x778E = 3  -> "I2C Fehlerflag EEPROM GWG"
    No verified value table for 0x778E is present in the source catalog. Keep
    value 3 as a raw diagnostic flag; do not infer that it means an active
    EEPROM fault.

    0xA395 len4 = 00 02 50 00:
      byte1 bit 0x02 -> Speicher CFDM = true
      byte2 bit 0x08 -> SP CFDM = false
      byte2 bit 0x01 -> HarteSperre CFDM = false
      byte2 bit 0x04 -> Fehler CFDM = false
      byte2 also contains 0x10 and 0x40, whose meanings are not exposed by
      the VDensHO1 catalog used here.

    0xA132 len29 =
      00 00 00 00 00 00 00 00 00 00 00 00 19 17 31 01 EA 07
      09 16 10 1E 23 00 00 00 00 00 00
      bytes12..13 little-endian -> alarm identifier 0x1719
      byte14 = 0x31; documented masks include Fehlermanager 0x20 and
               Veraenderung 0x10, both set in this sample
      byte15 = 1 -> participant number
      bytes16..17 little-endian -> year 2026
      byte18..22 -> 09-22 16:30:35
      byte27 = 0 -> disturbed-participant number
      byte28 = 0 -> current alarm error code
    The timestamp matched the live controller time at readout, so do not label
    it "last fault time". Only the current error-code byte is promoted.

  Burner/control-chain live verification (2026-09-22, continuous firing):
    A305 raw 0x42 -> 33.0 percent burner modulation.
    A307 raw 9C18 -> little-endian 0x189C = 6300 /100 = 63.0 C.
    A391 raw 9C18 -> little-endian 0x189C = 6300 /100 = 63.0 C.
    0x55E0 len17:
      01 76 02 00 00 22 01 00 05 51 76 02 00 00 43 01 02
      bytes10..11 = 76 02 -> little-endian 0x0276 = 630 /10 = 63.0 C.
    A38F raw 3F01 -> byte0 0x3F /2 = 31.5 percent, byte1=1 (EIN).
    A38F briefly reached 4201 -> 33.0 percent, byte1=1.
    55D3 while firing ended in 21 0B62 00:
      byte5 flame bit set; bytes6..7 0x0B62 = 2914 rpm.
    At the shutdown transition CFDM setpoint A391 changed to D80E:
      little-endian 0x0ED8 = 3800 /100 = 38.0 C.
    On the next sample A307 also read D80E and 55E0 bytes10..11 were 7C01:
      little-endian 0x017C = 380 /10 = 38.0 C.
    A38F then became 0000 and A305 00. Because the debug loop performs
    sequential bus reads, the exact sub-second ordering inside a printed line
    is not atomic; the value correspondence itself is hardware-confirmed.

  Heating-circuit-to-burner setpoint-chain verification (2026-09-22):
    Same active-heating state, hardware read:
      0x2544 = F4 01 -> VT_SolltemperaturA1M1 = 50.0 C.
      0x2900 = AE 01 -> VorlauftemperaturM1 = 43.0 C actual.
      0x555A = F4 01 -> effective boiler setpoint = 50.0 C.
      0x55E0 bytes10..11 = F4 01 -> RKR boiler setpoint = 50.0 C.
      0xA391 = 88 13 -> CFDM effective setpoint = 50.0 C.
      0xA307 = 88 13 -> BLR effective setpoint = 50.0 C.
    Therefore the source-side A1 flow setpoint and every verified downstream
    boiler/controller setpoint were identical at 50.0 C in this sample:
      A1 VT Soll (0x2544)
        -> Kesselsoll effektiv (0x555A)
        -> RKR KTSoll (0x55E0)
        -> CFDM EffectSetpt (0xA391)
        -> BLR EffectSetpt (0xA307)
    The measured A1 flow temperature was 43.0 C, i.e. 7.0 K below setpoint at
    the instant of the sequential reads.
    This sample shows no additional boiler-setpoint uplift between 0x2544 and
    0x555A. Do not generalize that to all operating modes without further
    captures; DHW, mixer circuits, frost protection or other controller logic
    may alter the relationship.

  HCC1/RKR local control-path verification (2026-09-22, active heating):
    HCC1 external/input-side object:
      0xA400 = FF -> nviHCC1 ApplicMode = HVAC_NUL.
      0xA401 = D0 07 -> nviHCC1 SpaceSetpt = 20.00 C.
      0xA403 = D0 07 -> nviHCC1 FlowSetpt = 20.00 C.
    HCC1 local/output-side object:
      0xA405 = 00 -> nvoHCC1 UnitState = HVAC_AUTO.
      0xA406 = 34 08 -> nvoHCC1 EffRoomSetpt = 21.00 C.
    Heating-circuit status block 0x2500 len22:
      02 02 BB 51 01 00 F4 01 01 00 00 01 D2 00 00 00 00 F4 01 00 D2 00
      byte1 = 0x02 -> Normalbetrieb.
      bytes12..13 = D2 00 -> 21.0 C active room setpoint, matching A406.
      bytes6..7 also contain F4 01 (=500 little-endian), which numerically
      matches the 50.0 C heating-generator setpoint in this sample, but no
      trusted VDensHO1 field definition was found for those bytes. Keep them
      unnamed; do not promote them.

    Local heat-generator setpoint chain in the same sample:
      0x555A = F4 01 -> effective boiler setpoint = 50.0 C.
      0x55E0 bytes10..11 = F4 01 -> RKR boiler setpoint = 50.0 C.
      0xA391 = 88 13 -> CFDM effective setpoint = 50.0 C.
      0xA307 = 88 13 -> BLR effective setpoint = 50.0 C.
    This hardware-confirms a common 50.0 C setpoint propagated through
    boiler/RKR -> CFDM -> BLR. The explicit A1 flow-setpoint datapoint
    0x2544 (VT_SolltemperaturA1M1, div10) is already in the production
    profile and is the next source-side value to compare against this chain.

  CFDM local-vs-external input verification (2026-09-22, burner firing):
    0xA380 len2 = 00 FF -> nviProdCmd CFDM: 0 percent, state AUTO.
    0xA383 len2 = 00 00 -> nviSetpoint CFDM: 0.00 C.
    0xA391 len2 = 88 13 -> effective CFDM setpoint 50.00 C.
    0xA38F len2 = 7F 01 -> effective CFDM power 63.5 percent, state EIN.
    0xA305 len1 = 80 -> BLR modulation 64.0 percent.
    0x55D3 = 41 9C A7 00 00 21 0B 62 00:
      byte0=65 fine GFA control/power value,
      flame bit set, fan=0x0B62=2914 rpm.
    Together with the previous A382=FF and A385=0000 observations during the
    heating start, this proves the nvi CFDM fields A380/A382/A383/A385 are not
    the active local command path on this WB2A. They are consistent with
    external/LON-style inputs while the local controller computes A391/A38F
    internally. Do not use them to explain or control the normal heating path.

  CFDM/GFA exported-interface spot check (2026-09-22, burner idle):
    0xA382 len1 = FF -> nviApplicMode CFDM = HVAC_NUL.
    0xA385 len2 = 0000 -> nviConsumerDmd Temp CFDM = 0.00 C.
    0xA307 len2 = D80E -> BLR effective setpoint = 38.00 C.
    0xA391 len2 = D80E -> CFDM effective setpoint = 38.00 C.
    0x55DD len1 = 01 -> GWG_Flamme1 bit 0x20 clear.
    0x55D3 len9 = 00 A9 A5 00 00 01 00 00 00:
      byte5 is also 0x01, so its flame bit 0x20 is clear as well.
    Thus the two documented flame indicators agree in this sample. The idle
    CFDM input demand is zero while the downstream BLR/CFDM effective
    setpoints retain the previously observed 38 C floor/default setpoint.

  GFA internal process-address reachability test (2026-09-22):
    0x7650 len1 -> raw 0x20, hardware-confirming GFA identifier 0x20.
    Vitosoft groups its internal FA process values by chip family:
      20h - GFA: P09 Modulationssollwert @ 0x4009,
                 P89 60-Hz-Betrieb @ 0x4059
      21h - SCOT / 23h - CES: broader P00..Pxx process-value sets.
    Direct Optolink reads on this WB2A returned retcode 3 for every tested
    length (1, 2, 4 bytes) at:
      0x4050 P80 FA-chip identifier
      0x4009 P09 modulation setpoint
      0x4059 P89 60-Hz status
    Therefore the VSKO internal 0x4000 process-value address space is not
    directly readable through this controller's normal Optolink path. Do not
    add these addresses to the production poll list.

  Full fast burner-cycle capture (2026-09-22 18:02:59..18:09:12):
    The capture started during the end of a DHW phase:
      18:04:59.580  A395 Speicher-CFDM bit cleared
      18:05:03.965  diverter 0x0A10 changed WW -> HEIZEN
      delta = 4.385 s

    Heating burner start:
      18:05:59.226  55D3 bytes6..7 = 0x0820 -> 2080 rpm, flame still off
      18:06:08.496  bytes6..7 = 0x0F50 -> 3920 rpm, byte5=0x09
      18:06:08.942  flame bit set; bytes6..7 = 0x0B60 -> 2912 rpm
      18:06:10.089  A305 first nonzero = 66%; A395 becomes 00 00 50 00
      18:06:11.530  A38F becomes 0x8201 -> 65%; CFDM state EIN
    Thus the observed ordering is fan pre-purge -> short speed increase ->
    flame -> A305 modulation -> A38F CFDM power/state. Requests are sequential,
    so quoted sub-second deltas are upper-resolution observations, not atomic
    controller event times.

    Controlled modulation:
      A305 ramped from 66% down to 33%.
      A38F followed from 65% down to 31.5%.
      55D3 byte0 closely followed the same trend: approx. 0x45=69 at the high
      end and 0x26=38 at A305=33%.
    Historical OpenV/vcontrold configurations also treat 55D3 byte0 as a fine
    burner-power/modulation-style value. On this appliance it is already
    nonzero during pre-purge (0x09 -> 0x46 before flame), so it must not be
    interpreted as delivered thermal power. Promote only as a diagnostic
    "GFA Leistungs-/Ansteuerwert fein".

    Shutdown:
      18:07:09.674  BLR setpoint A307 changes 50 -> 38 C, flame still on
      18:07:10.544  A305 changes 33 -> 0%; flame still on, fan 2914 -> 2418
      18:07:11.628  A38F -> 0/off, flame clears, fan -> 0
      18:07:12.553  55D3 byte0 decays 0x26 -> 0x0A
      18:07:15.365  55D3 byte0 reaches 0
      18:08:09.752  A395 00 00 50 00 finally returns to 00 00 00 00
    So the undocumented A395 byte2 bits 0x10/0x40 persist for about 58 s after
    flame-off; do not map them without source documentation.

    A393 nvoSupplyTemp_CFDM is hardware-confirmed:
      across the capture it tracks 0x0810 boiler temperature extremely closely.
      Mean A393-0x0810 difference = +0.04 K; mean absolute difference = 0.14 K;
      largest observed absolute delta = 1.2 K. The reads are sequential and
      A393/0x0810 change during the cycle, so small differences are expected.

    55D3 unknown bytes:
      byte1 has a very strong inverse relationship to boiler temperature
      (idle Pearson r about -0.998). A simple empirical transform
      T ~= 102.4 - 0.4*byte1 is close to the measured water temperature, but
      no VDensHO1/Vitosoft field definition tying byte1 to a temperature was
      found. Keep byte1 raw/unexposed.
      byte2 stayed almost entirely 0x9F (and 0xA0 at parts of WW/fully cooled
      state). Its meaning remains unknown. Do not label it.

  GFA error/event archive hardware verification:
    Slots 01..20 at 0x7590..0x763B all accept 9-byte reads.
    Layout is code byte + 8-byte BCD DateTime (YYYY MM DD weekday HH MM SS).
    Observed newest entries:
      01: code 0x00 @ 2026-09-21 19:22:40
      02: code 0x21 @ 2026-09-21 19:22:40
      03: code 0x98 @ 2026-09-21 17:31:44
      04: code 0x00 @ 2026-05-14 16:32:00
      05: code 0x04 @ 2026-05-14 16:27:44
    Older slots mostly alternate 0x00/0x21 around 2026-05-14 15:23..15:28.
    The GFA code space is distinct from the Vitotronic display fault codes.
    No complete public GFA-code table is available; do not map 0x00 to "OK".

    Research on observed codes (2026-09-22):
      Important: the archive code -> coding-address-38 relation is strongly
      suggested by both belonging to the internal GFA/VSKO code space, but no
      source found explicitly states that FehlerHisFA byte0 is identical to
      coding address 38 for every controller generation. Keep raw code as the
      authoritative value and treat these labels as source-backed candidates.

      0x04 = decimal 4:
        Viessmann Customer Care states VSKO/internal code 4 accompanies display
        fault F4. The WB2A service manual defines F4 as burner fault because no
        flame signal is present. Candidate meaning: no flame formation/signal.

      0x98 = decimal 152:
        Multiple Viessmann support cases explicitly pair coding address 38:152
        with display fault F9. The WB2A service manual defines F9 as fan speed
        too low at burner start. Candidate meaning: fan target speed not
        reached / fan control problem.

      0x21 = decimal 33:
        Viessmann support repeatedly describes coding address 38:33 as an
        internal supply-voltage under-supply / controller fault; after external
        mains supply is ruled out, replacement of the control unit is advised.
        Candidate meaning: internal control-supply undervoltage/status 33.

      0x00:
        observed repeatedly at exactly the same timestamps as 0x21 entries.
        This pattern is compatible with a clear/recovery transition, but no
        source proving that interpretation was found. Keep 0x00 unmapped.

    Additional post-burn 0x55D3 observation:
      After A305/A38F had gone to zero, the 9-byte GFA block continued changing:
        00 63 8A 00 00 01 00 00 00
        ...
        00 A8 97 00 00 01 00 00 00
      byte5 remained 0x01 (flame bit 0x20 clear, lockout bit 0x40 clear) and
      bytes6..7 stayed 0 rpm. Bytes1/2 therefore contain live internal values
      unrelated to flame/lockout/blower RPM, but no VDensHO1 field names for
      those bytes were found. Do not expose them with guessed semantics.

  Outdoor-temperature comparison:
    0x0800 = 13.6 C, 0x5525 = 13.8 C, 0x5527 = 14.4 C, with 0x083A=0 (sensor OK).
    0x0800 is hardware-readable on this exact SW03 controller even though it is
    absent from the Vitosoft-derived VDensHO1 catalog; community vcontrold and
    SmartHomeNG definitions identify it as the direct outdoor temperature.
    0x5525 is the low-pass outdoor temperature and 0x5527 the damped/mixed
    outdoor temperature used by the controller. Keep all three as distinct
    read-only values; do not alias them.
'''

poll_interval = 2

poll_groups = {
    "ONCE": 0,
    "FAST": 1,           # ~2 s
    "NORMAL": 15,        # ~30 s
    "SLOW": 150,         # ~5 min
    "RARE": 900,         # ~30 min

    # Optional hardware. M2, solar and hydraulic separator are confirmed absent.
    # VTS/VLTS and M1 room-sensor inputs are not valid on this installation.
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
    ('NORMAL', 'km_fehler_pumpe_a1', 0x0A33, 1, 1, False),  # HW=0
    ('NORMAL', 'km_fehler_interne_pumpe', 0x0A35, 1, 1, False),  # HW=0
    ('NORMAL', 'aktueller_gfa_fehlerstatus', 0x5738, 1, 1, False),  # HW=0
    ('SLOW', 'eeprom_status', 0x778B, 4, 'b:0:0', 1, False),  # HW=0
    ('ONCE', 'regelungssoftware_version_raw', 0x778B, 4, 'b:1:2::big', 1, False),  # 0x0103 -> 1.3
    ('SLOW', 'i2c_eeprom_gwg_flag', 0x778B, 4, 'b:3:3', 1, False),  # HW=3, meaning table unavailable
    ('NORMAL', 'cfdm_harte_sperre', 0xA395, 4, 'b:2:2:0x01', 'bool', False),  # HW false
    ('NORMAL', 'cfdm_fehler', 0xA395, 4, 'b:2:2:0x04', 'bool', False),  # HW false
    ('NORMAL', 'aktueller_alarm_fehlercode', 0xA132, 29, 'b:28:28', 1, False),  # HW=0
    ('ONCE', 'device_ident_raw', 0x00F8, 8),  # HW verified: 20c2000300000103
    ('ONCE', 'anlagenschema', 0x7700, 1, 1, False),  # HW verified: 2=A1+WW
    ('ONCE', 'anlagentyp', 0x7701, 1, 1, False),  # HW observed via 0x7700 len2: 1=Einkessel
    ('ONCE', 'codierstecker_sachnummer_raw', 0x1010, 7),  # HW verified ASCII: 7833971
    ('ONCE', 'codierstecker_kennung_raw', 0x1040, 2),  # HW verified raw: 0215; catalog rotatebytes
    ('ONCE', 'bedienteil_sw_index', 0x7330, 1, 1, False),  # HW verified: 1
    ('ONCE', 'gfa_kennung', 0x7650, 1, 1, False),  # HW verified: 0x20
    ('ONCE', 'bauart_warmwasser', 0x8851, 1, 1, False),  # HW verified: 0=Speicher
    ('ONCE', 'codierstecker_block_1050_raw', 0x1050, 16),  # HW verified raw block
    ('ONCE', 'codierstecker_bauart_warmwasser', 0x1050, 16, 'b:1:1', 1, False),  # GWG51=0 Umlaufwasserheizer
    ('ONCE', 'codierstecker_brennertyp', 0x1050, 16, 'b:3:3', 1, False),  # GWG53=2 modulierender Brenner
    ('ONCE', 'codierstecker_kesselsoll_max', 0x1050, 16, 'b:8:8', 1, False),  # HW: 74 C
    ('ONCE', 'codierstecker_kesselsoll_min', 0x1050, 16, 'b:9:9', 1, False),  # HW: 20 C
    ('ONCE', 'codierstecker_wwsoll_max', 0x1050, 16, 'b:10:10', 1, False),  # HW: 63 C absolute capability
    ('ONCE', 'codierstecker_wwsoll_min', 0x1050, 16, 'b:11:11', 1, False),  # HW: 10 C
    ('ONCE', 'codierstecker_ww_max_leistung', 0x1050, 16, 'b:12:12', 1, False),  # HW: 65%
    ('ONCE', 'codierstecker_heizung_max_leistung', 0x1050, 16, 'b:13:13', 1, False),  # HW: 65%
    ('ONCE', 'codierstecker_block_1020_raw', 0x1020, 16),  # HW: 0000ffffff0000000000000000000000; date bytes are FF/unset
    ('ONCE', 'codierstecker_block_1030_raw', 0x1030, 16),  # HW: 41be1de203fc51ae649b00ff00ff00ff
    ('ONCE', 'codierstecker_ww_leistungsbegrenzung', 0x1030, 16, 'b:0:0', 1, False),  # GWG30=65%
    ('ONCE', 'codierstecker_heizung_leistungsbegrenzung', 0x1030, 16, 'b:2:2', 1, False),  # GWG32=29%
    ('ONCE', 'codierstecker_umschaltventil_bauart', 0x1030, 16, 'b:4:4', 1, False),  # GWG34=3 Grundfos
    ('ONCE', 'codierstecker_block_1060_raw', 0x1060, 16),  # HW verified: 04081e0405041e140000000000000000
    ('ONCE', 'codierstecker_brenner_einschaltdifferenz', 0x1060, 16, 'b:0:0', 1, False),  # GWG60=4 K
    ('ONCE', 'codierstecker_brenner_ausschaltdifferenz', 0x1060, 16, 'b:1:1', 1, False),  # GWG61=8 K
    ('ONCE', 'codierstecker_kt_regler_verstaerkung', 0x1060, 16, 'b:2:2', 0.1, False),  # GWG62=3.0 %/K
    ('ONCE', 'codierstecker_kt_regler_nachstellzeit', 0x1060, 16, 'b:3:3', 10, False),  # GWG63=40 s
    ('ONCE', 'codierstecker_brenner_ausschaltdifferenz_volllast', 0x1060, 16, 'b:4:4', 1, False),  # GWG64=5 K
    ('ONCE', 'codierstecker_brenner_mindestpausenzeit', 0x1060, 16, 'b:5:5', 1, False),  # GWG65=4 min
    ('ONCE', 'codierstecker_brenner_pausenabbruch_differenz', 0x1060, 16, 'b:6:6', 1, False),  # GWG66=30 K
    ('ONCE', 'codierstecker_brenner_pausenabbruch_temperatur', 0x1060, 16, 'b:7:7', 1, False),  # GWG67=20 C
    ('ONCE', 'codierstecker_block_1070_raw', 0x1070, 16),  # HW verified raw: 051d141841323c000000000000000000
    ('ONCE', 'codierstecker_kesseltemperatur_min', 0x1070, 16, 'b:0:0', 1, False),  # HW: GWG70=5 C
    ('ONCE', 'codierstecker_brenner_min_leistung', 0x1070, 16, 'b:1:1', 1, False),  # HW: GWG71=29%
    ('ONCE', 'codierstecker_brenner_offset', 0x1070, 16, 'b:2:2', 1, False),  # HW: GWG72=20 K
    ('ONCE', 'codierstecker_brenner_anfahroptimierung', 0x1070, 16, 'b:3:3', 10, False),  # HW: GWG73=240 s
    ('ONCE', 'codierstecker_kesselsollleistung_speicherbetrieb', 0x1070, 16, 'b:4:4', 1, False),  # HW: GWG74=65%
    ('ONCE', 'codierstecker_interne_pumpe_min_drehzahl', 0x1070, 16, 'b:5:5', 1, False),  # HW: GWG75=50%
    ('ONCE', 'codierstecker_interne_pumpe_nachlauf', 0x1070, 16, 'b:6:6', 1, False),  # HW: GWG76=60 s
    ('ONCE', 'codierstecker_block_1080_raw', 0x1080, 16),  # HW: 04081e28370003080000000000000000
    ('ONCE', 'codierstecker_dlh_ausschaltdifferenz_start_stop', 0x1080, 16, 'b:0:0', 1, False),  # GWG80=4 K
    ('ONCE', 'codierstecker_dlh_einschaltdifferenz_start_stop', 0x1080, 16, 'b:1:1', 1, False),  # GWG81=8 K
    ('ONCE', 'codierstecker_dlh_nachlaufzeit', 0x1080, 16, 'b:2:2', 1, False),  # GWG82=30 s
    ('ONCE', 'codierstecker_dlh_max_anstiegszeit', 0x1080, 16, 'b:3:3', 1, False),  # GWG83=40 s
    ('ONCE', 'codierstecker_dlh_reglerverstaerkung', 0x1080, 16, 'b:4:4', 0.1, False),  # GWG84=5.5 %/K
    ('ONCE', 'codierstecker_dlh_reglervorhaltezeit', 0x1080, 16, 'b:5:5', 10, False),  # GWG85=0 s
    ('ONCE', 'codierstecker_dlh_reglernachstellzeit', 0x1080, 16, 'b:6:6', 10, False),  # GWG86=30 s
    ('ONCE', 'codierstecker_dlh_ausschaltdifferenz', 0x1080, 16, 'b:7:7', 1, False),  # GWG87=8 K
    ('ONCE', 'codierstecker_zirkulationspumpe_bei_speicherladung', 0x1080, 16, 'b:8:8', 1, False),  # GWG88=0 Regelfunktion
    ('ONCE', 'codierstecker_block_10c0_raw', 0x10C0, 16),  # HW: 5a322dc85a320232023200ffffffffff
    ('ONCE', 'codierstecker_grundfos_uv_schrittzahl_x1', 0x10C0, 16, 'b:0:0', 1, False),  # GWGC0=90
    ('ONCE', 'codierstecker_grundfos_uv_frequenz_x1', 0x10C0, 16, 'b:1:1', 1, False),  # GWGC1=50
    ('ONCE', 'codierstecker_grundfos_uv_schrittzahl_x2', 0x10C0, 16, 'b:2:2', 2, False),  # GWGC2=90 (45*2)
    ('ONCE', 'codierstecker_grundfos_uv_frequenz_x2', 0x10C0, 16, 'b:3:3', 2, False),  # GWGC3=400 (200*2)
    ('ONCE', 'codierstecker_grundfos_uv_schrittzahl_x3', 0x10C0, 16, 'b:4:4', 1, False),  # GWGC4=90
    ('ONCE', 'codierstecker_grundfos_uv_frequenz_x3', 0x10C0, 16, 'b:5:5', 1, False),  # GWGC5=50
    ('ONCE', 'codierstecker_grundfos_uv_schrittzahl_x4', 0x10C0, 16, 'b:6:6', 1, False),  # GWGC6=2
    ('ONCE', 'codierstecker_grundfos_uv_frequenz_x4', 0x10C0, 16, 'b:7:7', 1, False),  # GWGC7=50
    ('ONCE', 'codierstecker_grundfos_uv_schrittzahl_x5', 0x10C0, 16, 'b:8:8', 1, False),  # GWGC8=2
    ('ONCE', 'codierstecker_grundfos_uv_frequenz_x5', 0x10C0, 16, 'b:9:9', 1, False),  # GWGC9=50
    ('ONCE', 'codierstecker_grundfos_uv_position_heizen', 0x10C0, 16, 'b:10:10', 1, False),  # GWGCA=0
    ('ONCE', 'codierstecker_block_1090_raw', 0x1090, 16),  # HW verified: 002121212f373f48515a640000000000
    ('ONCE', 'codierstecker_brennerkennlinie_10', 0x1090, 16, 'b:1:1', 1, False),  # GWG91=33%
    ('ONCE', 'codierstecker_brennerkennlinie_20', 0x1090, 16, 'b:2:2', 1, False),  # GWG92=33%
    ('ONCE', 'codierstecker_brennerkennlinie_30', 0x1090, 16, 'b:3:3', 1, False),  # GWG93=33%
    ('ONCE', 'codierstecker_brennerkennlinie_40', 0x1090, 16, 'b:4:4', 1, False),  # GWG94=47%
    ('ONCE', 'codierstecker_brennerkennlinie_50', 0x1090, 16, 'b:5:5', 1, False),  # GWG95=55%
    ('ONCE', 'codierstecker_brennerkennlinie_60', 0x1090, 16, 'b:6:6', 1, False),  # GWG96=63%
    ('ONCE', 'codierstecker_brennerkennlinie_70', 0x1090, 16, 'b:7:7', 1, False),  # GWG97=72%
    ('ONCE', 'codierstecker_brennerkennlinie_80', 0x1090, 16, 'b:8:8', 1, False),  # GWG98=81%
    ('ONCE', 'codierstecker_brennerkennlinie_90', 0x1090, 16, 'b:9:9', 1, False),  # GWG99=90%
    ('ONCE', 'codierstecker_brennerkennlinie_100', 0x1090, 16, 'b:10:10', 1, False),  # GWG9A=100%
    ('ONCE', 'hydraulische_weiche_vorhanden', 0x7752, 1, 1, False),  # HW verified: 0=nicht vorhanden
    ('ONCE', 'solar_typ', 0x7754, 1, 1, False),  # HW verified: 0=ohne

    # ---------------------------------------------------------------------
    # Core temperatures
    # VDensHO1 catalog uses the filtered sensor values for diagnosis.
    # ---------------------------------------------------------------------
    ('FAST', 'aussentemperatur', 0x0800, 2, 0.1, True),  # HW verified: 13.6 C; direct outdoor temperature
    ('NORMAL', 'aussentemperatur_tiefpass', 0x5525, 2, 0.1, True),  # HW verified: 13.8 C
    ('NORMAL', 'aussentemperatur_gedaempft', 0x5527, 2, 0.1, True),  # HW verified: 14.4 C

    ('FAST', 'kesseltemperatur', 0x0810, 2, 0.1, True),  # HW verified: 31.0 C
    ('FAST', 'kessel_solltemperatur', 0x555A, 2, 0.1, True),  # HW verified dynamically: 30.0->19.0->20.9->22.7->5.0 C
    ('NORMAL', 'abgastemperatur', 0x0816, 2, 0.1, True),  # HW verified: 31.6 C

    ('FAST', 'warmwasser_temperatur', 0x0812, 2, 0.1, True),  # HW verified: 43.3 C
    ('NORMAL', 'warmwasser_solltemperatur', 0x6300, 1, 1, False),  # HW verified R/W: 45->44->45 C
    ('NORMAL', 'warmwasser_solltemperatur_aktuell', 0x6500, 2, 0.1, True),  # HW verified: 45.0 C

    ('OPTIONAL_EXT', 'hydraulische_weiche_temperatur', 0x080C, 2, 0.1, True),  # HW default 20.0 C; 0x7752=0 confirms no physical separator
    ('OPTIONAL_EXT', 'vorlaufsensor_vts_temperatur', 0x081A, 2, 0.1, True),  # HW default 20.0 C; 0x0840=2 open circuit
    ('OPTIONAL_EXT', 'sts2_temperatur', 0x0814, 2, 0.1, True),  # HW default 20.0 C; 0x083D=2 open circuit

    # Sensor diagnostics
    ('SLOW', 'sensorstatus_aussentemperatur', 0x083A, 1, 1, False),  # HW verified: 0=OK
    ('SLOW', 'sensorstatus_kesseltemperatur', 0x083B, 1, 1, False),  # HW verified: 0=OK
    ('SLOW', 'sensorstatus_sts2', 0x083D, 1, 1, False),  # HW verified: 2=Unterbrechung
    ('SLOW', 'sensorstatus_vlts', 0x0840, 1, 1, False),  # HW verified: 2=Unterbrechung
    ('SLOW', 'sensorstatus_raum_m1', 0x089C, 1, 1, False),  # HW verified: 3=Referenzfehler
    ('OPTIONAL_M2', 'sensorstatus_raum_m2', 0x089D, 1, 1, False),  # HW verified: 3=Referenzfehler; M2 absent
    ('ONCE', 'heizkreis_m1_reglervariante', 0x2521, 1, 1, False),  # HW verified: 2=witterungsgefuehrt
    ('ONCE', 'heizkreis_m2_reglervariante', 0x3521, 1, 1, False),  # HW verified: 5=nicht vorhanden

    # ---------------------------------------------------------------------
    # Burner / pumps / valves
    # ---------------------------------------------------------------------
    ('FAST', 'brenner_modulationsgrad', 0xA305, 1, 0.5, False),  # HW verified dynamically: 66->53->36->33%, then 0% at flame-off

    # One two-byte read can feed both state and speed.
    ('FAST', 'interne_pumpe_status', 0x7660, 2, 'b:0:0', 1, False),  # HW verified dynamically: 1 during firing/post-run, 0 while idle
    ('FAST', 'interne_pumpe_drehzahl', 0x7660, 2, 'b:1:1', 1, False),  # HW verified: 100% firing, 50% post-run

    ('FAST', 'heizkreis_m1_pumpe_ausgang', 0x7663, 2, 'b:0:0', 1, False),  # HW verified: 1 firing, 0 after flame-off
    ('FAST', 'heizkreis_m1_pumpe_drehzahl', 0x7663, 2, 'b:1:1', 1, False),  # HW verified: 100% firing, 0% after flame-off
    ('FAST', 'heizkreis_m1_pumpe_status', 0x2906, 1, 1, False),  # HW verified logical state; remained 1 after physical 0x7663 output stopped
    ('FAST', 'speicherladepumpe_status', 0x6513, 1, 1, False),  # HW verified: 0=OFF
    ('FAST', 'warmwasser_ladestatus', 0x650A, 1, 1, False),  # HW verified: 0=Ladung inaktiv
    ('FAST', 'zirkulationspumpe_status', 0x6515, 1, 1, False),  # HW verified: 1
    ('FAST', 'umschaltventil_stellung', 0x0A10, 1, 1, False),  # HW verified dynamically: 3=WW earlier, 1=Heizen now
    ('FAST', 'relais_k12_status', 0x0842, 1, 1, False),  # HW verified: 1
    ('NORMAL', 'warmwasser_flowswitch', 0x0883, 1, 1, False),  # HW verified: OFF

    # One 9-byte fire-control block feeds blower speed, flame and lockout.
    # Keep these entries consecutive so optolink-splitter performs one shared
    # read and applies the byte/bit filters to the same response.
    ('FAST', 'geblaesedrehzahl', 0x55D3, 9, 'b:6:7::big', 1, False),  # HW verified: 2080 rpm pre-purge, ~2912 rpm firing, 0 rpm idle
    ('FAST', 'brenner_flamme', 0x55D3, 9, 'b:5:5:0x20', 'bool', False),  # HW verified dynamically against firing cycle
    ('FAST', 'feuerungsautomat_verriegelt', 0x55D3, 9, 'b:5:5:0x40', 'bool', False),  # HW verified block readable

    # Alternative direct flame flag from the fire-control diagnostic block.
    ('NORMAL', 'brenner_flamme_gfa', 0x55DD, 1, 'b:0:0:0x20', 'bool', False),  # HW verified dynamically; matches 0x55D3 flame

    # ---------------------------------------------------------------------
    # Heating circuit A1/M1 - operating state
    # ---------------------------------------------------------------------
    ('NORMAL', 'heizkreis_m1_bedienteil_betriebsart', 0x2323, 1, 1, False),  # HW verified R/W: 2=Heizen+WW, 4=Dauernd Normal
    ('NORMAL', 'heizkreis_m1_betriebsprogramm_aktuell', 0x2301, 1, 1, False),  # HW verified read: 3=Heizen+WW Schaltzeiten, 2=Normal dauernd
    ('NORMAL', 'heizkreis_m1_sparbetrieb', 0x2302, 1, 1, False),  # HW verified read; write ACKed but ignored
    ('NORMAL', 'heizkreis_m1_partybetrieb', 0x2303, 1, 1, False),  # HW verified R/W: 0=off, 1=on

    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_normal', 0x2306, 1, 1, False),  # HW verified R/W: 21->22->21 C
    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_reduziert', 0x2307, 1, 1, False),  # HW verified R/W: 18->19->18 C
    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_party', 0x2308, 1, 1, False),  # HW verified R/W: 21->22->21 C  # HW verified R/W: 21->22->21 C

    ('OPTIONAL_EXT', 'heizkreis_m1_raumtemperatur', 0x0896, 2, 0.1, True),  # HW default 20.0 C; 0x089C=3 reference error

    # One 22-byte state block feeds multiple A1/M1 entities.
    # Hardware sample: 02 01 00 00 00 00 00 00 01 00 00 01 B4 00 00 00 00 00 00 00 B4 00
    ('NORMAL', 'heizkreis_m1_betriebsart_aktuell', 0x2500, 22, 'b:1:1', 1, False),  # HW verified: 1=Reduziert, 2=Normal, 3=Dauernd Normal
    ('NORMAL', 'heizkreis_m1_raumsolltemperatur_aktuell', 0x2500, 22, 'b:12:13', 0.1, True),  # HW verified: 18.0 C reduced, 21.0 C party
    ('NORMAL', 'heizkreis_m1_frostgefahr', 0x2500, 22, 'b:16:16:0x01', 'bool', False),  # HW verified: false
    ('NORMAL', 'heizkreis_m1_ferienbetrieb', 0x2535, 1, 'b:0:0:0x01', 'bool', False),  # HW verified: false

    ('FAST', 'heizkreis_m1_vorlaufsolltemperatur', 0x2544, 2, 0.1, True),  # HW verified readable: 0.0 C outside heating window

    # ---------------------------------------------------------------------
    # Heating circuit A1/M1 - service coding
    # ---------------------------------------------------------------------
    ('SLOW', 'heizkreis_m1_speichervorrang_a2', 0x27A2, 1, 1, False),  # HW verified: 2=Speichervorrang
    ('SLOW', 'heizkreis_m1_frostgrenze_a3', 0x27A3, 1, 1, True),  # HW verified: -9 C
    ('SLOW', 'heizkreis_m1_frostschutz_a4', 0x27A4, 1, 1, False),  # HW verified: 0=aktiv
    ('SLOW', 'heizkreis_m1_sommerspar_schaltschwelle_a5', 0x27A5, 1, 1, False),  # HW verified: 5=AT > RTsoll + 1 K
    ('SLOW', 'heizkreis_m1_sommersparabschaltung_a6', 0x27A6, 1, 1, False),  # HW verified: 5 C
    ('SLOW', 'heizkreis_m1_mischersparfunktion_a7', 0x27A7, 1, 1, False),  # HW verified: 0=ohne
    ('SLOW', 'heizkreis_m1_pumpe_reduziert_a9', 0x27A9, 1, 1, False),  # HW verified: 7 min

    ('SLOW', 'heizkreis_m1_vorlauf_min_c5', 0x27C5, 1, 1, False),  # HW verified raw=0x26
    ('SLOW', 'heizkreis_m1_vorlauf_max_c6', 0x27C6, 1, 1, False),  # HW verified raw=0x32

    ('SLOW', 'heizkreis_m1_heizkennlinie_neigung_d3', 0x27D3, 1, 0.1, False),  # HW verified: 0.8
    ('SLOW', 'heizkreis_m1_heizkennlinie_niveau_d4', 0x27D4, 1, 1, True),  # HW verified: +5 K

    ('SLOW', 'heizkreis_m1_pumpentyp_e5', 0x27E5, 1, 1, False),  # HW verified: 0=stufig
    ('SLOW', 'heizkreis_m1_pumpe_max_drehzahl_e6', 0x27E6, 1, 1, False),  # HW verified: 100%
    ('SLOW', 'heizkreis_m1_pumpe_min_drehzahl_e7', 0x27E7, 1, 1, False),  # HW verified: 30%
    ('SLOW', 'heizkreis_m1_pumpe_nebenbetrieb_e8', 0x27E8, 1, 1, False),  # HW verified: 0=minimal nach E7
    ('SLOW', 'heizkreis_m1_pumpe_reduziert_e9', 0x27E9, 1, 1, False),  # HW verified: 50%

    ('SLOW', 'heizkreis_m1_temperaturprogramm_f1', 0x27F1, 1, 1, False),  # HW verified: 0=Passiv
    ('SLOW', 'heizkreis_m1_party_zeitbegrenzung_f2', 0x27F2, 1, 1, False),  # HW verified: 8 h
    ('EXPERIMENTAL', 'heizkreis_m1_reduziert_anhebung_start_f8', 0x27F8, 1, 1, True),  # HW P300 error on SW03
    ('EXPERIMENTAL', 'heizkreis_m1_reduziert_anhebung_ende_f9', 0x27F9, 1, 1, True),  # HW P300 error on SW03
    ('EXPERIMENTAL', 'heizkreis_m1_vorlauf_ueberhoehung_fa', 0x27FA, 1, 1, False),  # HW P300 error on SW03
    ('EXPERIMENTAL', 'heizkreis_m1_vorlauf_ueberhoehung_dauer_fb', 0x27FB, 1, 2, False),  # HW P300 error on SW03

    # ---------------------------------------------------------------------
    # Boiler / DHW service coding
    # ---------------------------------------------------------------------
    ('SLOW', 'kessel_maximaltemperatur_06', 0x5706, 1, 1, False),  # HW verified: 81 C
    ('SLOW', 'interne_pumpe_kennung_30', 0x5730, 1, 1, False),  # HW verified: 1=drehzahlgeregelt
    ('SLOW', 'interne_pumpe_solldrehzahl_31', 0x5731, 1, 1, False),  # HW verified: 100%

    ('SLOW', 'warmwasser_sollbereich_56', 0x6756, 1, 1, False),  # HW verified: 0=10..60 C
    ('SLOW', 'warmwasser_einschalt_offset_59', 0x6759, 1, 1, False),  # HW verified: 0=2.5 K below setpoint
    ('SLOW', 'warmwasser_speicher_anbindung_5b', 0x675B, 1, 1, False),  # HW verified: 0=vor Weiche
    ('SLOW', 'warmwasser_kessel_offset_60', 0x6760, 1, 1, False),  # HW verified: 20 K
    ('SLOW', 'warmwasser_pumpennachlauf_62', 0x6762, 1, 1, False),  # HW verified byte0=5 min; exact length1
    ('SLOW', 'umschaltventil_bauart_65', 0x6765, 1, 1, False),  # HW verified: 3=Grundfos Ventil

    ('SLOW', 'zirkulation_bei_ww_soll1_71', 0x6771, 1, 1, False),  # HW verified read: 0=Regelfunktion
    ('SLOW', 'zirkulation_bei_ww_soll2_72', 0x6772, 1, 1, False),  # HW verified read: 0=Regelfunktion
    ('SLOW', 'zirkulation_intervall_73', 0x6773, 1, 1, False),  # HW verified R/W: 0=Schaltuhr, 7=Dauernd EIN
    ('SLOW', 'relais_k12_funktion_53', 0x7753, 1, 1, False),  # HW verified: 1=Zirkulationspumpe

    # ---------------------------------------------------------------------
    # Counters / system time / errors
    # ---------------------------------------------------------------------
    ('RARE', 'brenner_starts', 0x088A, 4, 1, False),  # HW verified unsigned: 487265
    ('RARE', 'brenner_betriebsstunden', 0x08A7, 4, 0.0002777777777777778, False),  # HW verified: 17731.4 h
    ('RARE', 'brenner_betriebsstunden_stufe1', 0x0886, 4, 0.0002777777777777778, False),  # HW verified: 17731.4 h
    ('RARE', 'systemzeit', 0x088E, 8, 'vdatetime', False),  # HW verified R/W DateTimeBCD

    # Internal burner/controller chain, hardware verified live.
    ('NORMAL', 'cfdm_application_mode', 0xA382, 1, 1, False),  # idle FF=HVAC_NUL
    ('NORMAL', 'cfdm_consumer_demand_temperatur', 0xA385, 2, 0.01, False),  # idle 0000=0.00 C
    ('NORMAL', 'blr_kesselsolltemperatur_effektiv', 0xA307, 2, 0.01, False),  # 9c18=63.0 C, d80e=38.0 C
    ('NORMAL', 'cfdm_vorlauftemperatur', 0xA393, 2, 0.01, False),  # full-cycle HW verified vs 0x0810
    ('NORMAL', 'cfdm_kesselsolltemperatur_effektiv', 0xA391, 2, 0.01, False),  # same values as A307
    ('NORMAL', 'rkr_kesselsolltemperatur', 0x55E0, 17, 'b:10:11', 0.1, False),  # 7602=63.0 C, 7c01=38.0 C
    ('NORMAL', 'cfdm_leistungswert', 0xA38F, 2, 'b:0:0', 0.5, False),  # 3f=31.5%, 42=33%
    ('NORMAL', 'gfa_leistungs_ansteuerwert_fein', 0x55D3, 9, 'b:0:0', 1, False),  # HW: 69@A305=66%, 38@33%; nonzero pre-purge
    ('NORMAL', 'cfdm_leistungsstatus', 0xA38F, 2, 'b:1:1:0x01', 'bool', False),  # 1 firing, 0 off

    # Separate GFA error/event archive. Code byte + BCD timestamp; no code map.
    ('RARE', 'gfa_fehlerhistorie_01_raw', 0x7590, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_02_raw', 0x7599, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_03_raw', 0x75A2, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_04_raw', 0x75AB, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_05_raw', 0x75B4, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_06_raw', 0x75BD, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_07_raw', 0x75C6, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_08_raw', 0x75CF, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_09_raw', 0x75D8, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_10_raw', 0x75E1, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_11_raw', 0x75EA, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_12_raw', 0x75F3, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_13_raw', 0x75FC, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_14_raw', 0x7605, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_15_raw', 0x760E, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_16_raw', 0x7617, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_17_raw', 0x7620, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_18_raw', 0x7629, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_19_raw', 0x7632, 9, 'raw', False),
    ('RARE', 'gfa_fehlerhistorie_20_raw', 0x763B, 9, 'raw', False),

    ('RARE', 'fehlerhistorie_01', 0x7507, 9, 'b:0:0', 'f:02X', False),  # HW verified 9-byte slot readable
    ('RARE', 'fehlerhistorie_02', 0x7510, 9, 'b:0:0', 'f:02X', False),  # HW verified 9-byte slot readable
    ('RARE', 'fehlerhistorie_03', 0x7519, 9, 'b:0:0', 'f:02X', False),  # HW verified 9-byte slot readable
    ('RARE', 'fehlerhistorie_04', 0x7522, 9, 'b:0:0', 'f:02X', False),  # HW verified 9-byte slot readable
    ('RARE', 'fehlerhistorie_05', 0x752B, 9, 'b:0:0', 'f:02X', False),  # HW verified 9-byte slot readable
    ('RARE', 'fehlerhistorie_06', 0x7534, 9, 'b:0:0', 'f:02X', False),  # HW verified 9-byte slot readable
    ('RARE', 'fehlerhistorie_07', 0x753D, 9, 'b:0:0', 'f:02X', False),  # HW verified 9-byte slot readable
    ('RARE', 'fehlerhistorie_08', 0x7546, 9, 'b:0:0', 'f:02X', False),  # HW verified 9-byte slot readable
    ('RARE', 'fehlerhistorie_09', 0x754F, 9, 'b:0:0', 'f:02X', False),  # HW verified 9-byte slot readable
    ('RARE', 'fehlerhistorie_10', 0x7558, 9, 'b:0:0', 'f:02X', False),  # HW verified 9-byte slot readable

    # ---------------------------------------------------------------------
    # Time programs
    # ---------------------------------------------------------------------
    ('RARE', 'heizkreis_m1_zeitprogramm_montag', 0x2000, 8, 'schedvdens', False),  # HW verified: 05:00-20:00
    ('RARE', 'heizkreis_m1_zeitprogramm_dienstag', 0x2008, 8, 'schedvdens', False),  # HW verified: 05:00-20:00
    ('RARE', 'heizkreis_m1_zeitprogramm_mittwoch', 0x2010, 8, 'schedvdens', False),  # HW verified: 05:00-20:00
    ('RARE', 'heizkreis_m1_zeitprogramm_donnerstag', 0x2018, 8, 'schedvdens', False),  # HW verified: 05:00-20:00
    ('RARE', 'heizkreis_m1_zeitprogramm_freitag', 0x2020, 8, 'schedvdens', False),  # HW verified: 05:00-20:00
    ('RARE', 'heizkreis_m1_zeitprogramm_samstag', 0x2028, 8, 'schedvdens', False),  # HW verified: 05:00-20:00
    ('RARE', 'heizkreis_m1_zeitprogramm_sonntag', 0x2030, 8, 'schedvdens', False),  # HW verified: 05:00-20:00

    ('RARE', 'warmwasser_zeitprogramm_montag', 0x2100, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'warmwasser_zeitprogramm_dienstag', 0x2108, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'warmwasser_zeitprogramm_mittwoch', 0x2110, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'warmwasser_zeitprogramm_donnerstag', 0x2118, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'warmwasser_zeitprogramm_freitag', 0x2120, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'warmwasser_zeitprogramm_samstag', 0x2128, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'warmwasser_zeitprogramm_sonntag', 0x2130, 8, 'schedvdens', False),  # HW verified: 05:30-21:00

    ('RARE', 'zirkulation_zeitprogramm_montag', 0x2200, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'zirkulation_zeitprogramm_dienstag', 0x2208, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'zirkulation_zeitprogramm_mittwoch', 0x2210, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'zirkulation_zeitprogramm_donnerstag', 0x2218, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'zirkulation_zeitprogramm_freitag', 0x2220, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'zirkulation_zeitprogramm_samstag', 0x2228, 8, 'schedvdens', False),  # HW verified: 05:30-21:00
    ('RARE', 'zirkulation_zeitprogramm_sonntag', 0x2230, 8, 'schedvdens', False),  # HW verified: 05:30-21:00

    # ---------------------------------------------------------------------
    # Optional M2 heating circuit
    # ---------------------------------------------------------------------
    ('OPTIONAL_M2', 'heizkreis_m2_sparbetrieb', 0x3302, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_partybetrieb', 0x3303, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_raumtemperatur', 0x0898, 2, 0.1, True),  # HW default 20.0 C; schema confirms no M2
    ('OPTIONAL_M2', 'heizkreis_m2_vorlauftemperatur', 0x3900, 2, 0.1, True),  # HW 0.0 C; no M2
    ('OPTIONAL_M2', 'heizkreis_m2_vorlaufsolltemperatur', 0x3544, 2, 0.1, True),  # HW 0.0 C; no M2
    ('OPTIONAL_M2', 'heizkreis_m2_pumpe_status', 0x3906, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_pumpe_drehzahl', 0x7665, 2, 'b:1:1', 1, False),  # HW block 0000; no M2
    ('OPTIONAL_M2', 'heizkreis_m2_vorlauf_min_c5', 0x37C5, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_vorlauf_max_c6', 0x37C6, 1, 1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_heizkennlinie_neigung_d3', 0x37D3, 1, 0.1, False),
    ('OPTIONAL_M2', 'heizkreis_m2_heizkennlinie_niveau_d4', 0x37D4, 1, 1, True),

    # ---------------------------------------------------------------------
    # Optional solar
    # ---------------------------------------------------------------------
    ('OPTIONAL_SOLAR', 'solar_kollektortemperatur', 0x6564, 2, 0.1, True),  # HW invalid sentinel 3276.7 C; 0x7754=0 no solar
    ('OPTIONAL_SOLAR', 'solar_speichertemperatur', 0x6566, 2, 0.1, True),  # HW invalid sentinel 3276.7 C; no solar
    ('OPTIONAL_SOLAR', 'solarpumpe_status', 0x6552, 1, 1, False),  # HW 0; no solar controller
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
#   VDensHO1 clearly exposes read state at 0x2303 / 0x2302.
#   0x2302 is NOT an effective write register on this exact controller:
#   write 1 is ACKed at protocol level but immediate read-back remains 0 and
#   the live heating-circuit state block does not change.
#   Some other Viessmann generations use 0x2331 as an economy-mode command,
#   but 0x2331 is absent from the exact VDensHO1 Vitosoft-derived catalog.
#   Hardware probe on this 20C2/SW03 returned P300 retcode 3 for read 0x2331,
#   confirming that 0x2331 is not a usable ordinary datapoint here.
#   Native Party datapoint 0x2303 behavior on this exact generation:
#     - remote OFF (write 0) is reliable;
#     - remote ON (write 1) is ACKed but may immediately revert to 0;
#     - after one complete physical Party activation, remote ON can temporarily
#       work again;
#     - switching Party OFF at the physical control panel makes remote ON fail
#       again;
#     - writing 0x2308 after 0x2303 does not reproduce the missing local
#       confirmation/bedienpanel state;
#     - physical Party toggling changes 0x2303 and 0x2500 byte 8 as observed.
#   Therefore production must not depend on 0x2303=1 for Party activation.
#   Synthetic Party uses 0x2323=4 with saved/restored 0x2323 and 0x2306 values.
#   0x2330 is explicitly ruled out on this controller: a hardware write returned
#   P300 retcode 3 / payload 0x01.
#
#
# Party room setpoint:
#   0x2308 len1 is hardware-verified READ/WRITE on this exact appliance.
#   Tested 21 C -> 22 C -> 21 C with matching read-back and 0x2500 effective
#   room-setpoint changes. Safe HA number range should follow the controller
#   limits rather than an arbitrary wider range.
##
# Operating mode:
#   0x2323 len1 is hardware-verified READ/WRITE on this exact appliance.
#   Verified transition 2 (Heizen+WW) -> 4 (Dauernd Normal) -> 2, with matching
#   0x2301 and 0x2500 state changes. Values 0/1 were deliberately not tested.
#   0x2301 is read-only status: observed 3 for Heizen+WW according to timer and
#   2 for continuous normal heating.
##
# DHW setpoint:
#   0x6300 len1 is hardware-verified READ/WRITE on this exact appliance.
#   Verified 45 C -> 44 C -> 45 C with matching 0x6500 effective setpoint.
#   Current coding 0x6756=0 restricts the operational range to 10..60 C.
#   Coding-plug 0x1050 bytes10/11 advertise absolute capability 10..63 C.
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
