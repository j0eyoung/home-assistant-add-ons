# Debugging ESPHome devices

## First move: get the actual logs, don't theorize from symptoms

Most "my device is broken" questions resolve in the log output. Before suggesting fixes, ask for output from one of:

- `esphome logs my-device.yaml` — works for connected devices over network or serial
- USB-serial direct read at 115200 baud (or 74880 for ESP8266 boot messages) — needed when the device is in a boot loop and never reaches WiFi
- The Logs tab in the ESPHome dashboard
- HA's built-in log subscription: in HA Settings → Devices & services → ESPHome → Configure, enable "Subscribe to logs." Logs then appear in HA's logger at `homeassistant.components.esphome`.

Boot-loop logs at 74880 baud on ESP8266 are critical because the bootloader output is at that weird rate; switching to 115200 misses the part you actually need.

For ESP32 variants with USB-CDC (S3, C3 with USB jack, C6), boot logs come over USB at 115200 once the USB stack is up — but the very earliest bootloader output may be lost. Holding BOOT and pressing RESET to manually enter download mode often gets cleaner output.

**Log level and performance:** Setting `logger: level: VERY_VERBOSE` is useful for hardware communication debugging, but on single-core devices (ESP8266, ESP32-C3) high log verbosity can interfere with networking. Drop the log level once you've diagnosed the problem.

## Boot loops

Symptom: device prints a startup banner, sometimes a crash dump, then resets. Loops forever.

Triage in this order:

1. **Stack trace decode**: ESPHome prints something like `Backtrace: 0x40083ed1:0x3ffb1f60 0x4008c2a5:0x3ffb1f90 ...`. The `esphome` CLI usually decodes this automatically when you have the `.elf` file. If not, the addresses point to specific functions and tell you exactly which component crashed.
2. **Brownout detector triggers**: if logs mention `brownout detector was triggered`, the USB cable / PSU is undersized. ESP32 WiFi transmits pull ~500 mA peaks. Try a different cable first (cheap micro-USB cables drop voltage), then a 1 A+ supply. WiFi-heavy boards on a PC USB 2.0 port often brown out. Adding a capacitor (100–470 µF) across the power rails absorbs current spikes.
3. **Watchdog reset (`rst:0x8 (TG1WDT_SYS_RESET)` or similar)**: something blocked the main loop too long. Common culprits are long `delay()` in lambdas, or external components doing blocking I/O in `setup()` or `loop()`.
4. **OOM crash (`Guru Meditation Error: ... LoadProhibited` after `malloc` messages)**: you've outgrown RAM. Most likely on ESP8266 with too many entities, or on ESP32 with `bluetooth_proxy: active: true` + web_server + lots of sensors. Drop `web_server`, switch some entities to `internal: true`, or move to a bigger chip.
5. **Pin-related brick**: if you flashed a config that uses GPIO 6–11 on classic ESP32, the chip can't boot because those pins are wired to flash. Need to erase flash (`esptool.py erase_flash`) and re-flash a known-good config via the boot button.

## WiFi instability

Symptoms: device shows "unavailable" in HA periodically, logs show repeated connect/disconnect, OTA fails halfway.

Common causes and fixes, in roughly descending order of frequency:

- **Power supply** — same brownout story. WiFi peaks draw a lot; weak supply causes random disconnects rather than full crashes.
- **Power save interaction** — some routers + ESPs have a bad interaction with WiFi power-save. Set `wifi: power_save_mode: none` and see if it stabilizes. Costs a tiny bit more current. (Note: `power_save_mode: light` is the default and *may worsen* issues on some routers.)
- **CPU frequency** — on ESP32 variants, lowering the CPU frequency reduces peak current draw and can reduce brownout-induced disconnects: `esp32: cpu_frequency: 80MHz` instead of the default 240 MHz. Trade-off is slower processing.
- **Hidden SSID** — if your network is hidden, enable `wifi: fast_connect: true`. Without it, ESPHome does a full scan on every reconnect attempt, which is slow and unreliable with hidden SSIDs.
- **2.4 GHz congestion** — ESPs are 2.4-only. Crowded apartment buildings on channels 1/6/11 cause this. Try forcing a channel in `wifi:` config.
- **Bad antenna routing** — on dev boards with a PCB antenna, putting the board in a metal enclosure or near other 2.4 GHz devices tanks the signal. Check RSSI via the `wifi_signal:` sensor; below -75 dBm is dicey, below -85 dBm won't work.
- **DHCP lease expiration**: rare but happens. Set `manual_ip:` if the router is misbehaving, but a static DHCP lease in the router config is cleaner.

## OTA failures

OTA is HTTP-based and writes the new firmware to a second flash partition, then swaps. Failures:

- **"Connection refused" / "couldn't connect"** — device is unreachable. WiFi died, or you're on a different VLAN/subnet. Try `esphome run` with `--device <ip>` to bypass mDNS discovery.
- **"Bad magic byte" or hash mismatch** — the upload corrupted in transit, or the wrong binary type. Common on cheap WiFi. Retry once; if persistent, flash over USB.
- **"Not enough space"** — the new binary is bigger than the OTA partition. Happens after adding lots of features or switching frameworks. The fix is either trimming the build or doing a USB flash with a larger partition table.
- **Reboot loop right after OTA succeeds** — the new firmware has a bug that crashes early. ESPHome will auto-roll-back after a few failed boots (rollback partition), but if it doesn't, USB flash a known-good build.

## Sensor reading garbage / no readings

For I²C:

- Run an `i2c.scan` (set `scan: true` in the `i2c:` block) and check the logs at boot. The device address should appear. If nothing shows up, you have a wiring problem — usually missing pull-ups (some breakout boards include them, some don't, you need 4.7 kΩ to 3.3 V on SDA and SCL if the board doesn't have them).
- Wrong address — many sensors have a configurable address pin. BME280 is 0x76 or 0x77.
- 5 V sensor on a 3.3 V board — ESP GPIOs are not 5 V tolerant. You may have damaged the pin.
- Long wires + high frequency — drop `frequency:` in the `i2c:` block from the default 50 kHz down further, or use shorter wires.

For 1-wire (DS18B20):

- Missing 4.7 kΩ pull-up to 3.3 V on the data line. Always required.
- Parasitic power mode is unreliable on ESPHome — wire the 3-wire version (VCC, GND, data) properly.

For analog (ADC) on ESP32:

- ADC2 channels can't be used while WiFi is active (hardware limit). If `pin:` is on ADC2, switch to an ADC1 pin.
- ESP32 ADC is noisy and non-linear. Use `filters:` (median, sliding window) and consider an external ADC for precision.

## Memory exhaustion

`esphome logs` at startup prints free heap. Watch it. On ESP8266, you want ≥15 KB free after boot; ESP32, ≥40 KB. Below that, networking gets flaky.

Reducers in order of impact:

1. Disable `web_server` if not actively used — saves ~30 KB on ESP8266
2. Remove `captive_portal` once you've finished initial setup
3. Mark internal-only sensors with `internal: true` — they still cost RAM but skip HA-side state
4. Drop polling frequencies on chatty sensors
5. On ESP32, switch to `framework: type: esp-idf` — typically 20–40 KB lighter than Arduino
6. As a last resort, move to a chip with more RAM (any ESP32 variant beats ESP8266 here)

## State restore failures after reboot

If `restore_value: yes` globals or entity restore modes stop working after a reboot, the NVS (Non-Volatile Storage) flash partition may have overflowed. This happens silently. Fix:

```bash
# Wipe just the NVS partition (preserves firmware)
esptool.py --port /dev/ttyUSB0 read_flash 0x9000 0x5000 nvs.bin   # backup first
dd if=/dev/zero bs=1 count=20480 | esptool.py --port /dev/ttyUSB0 write_flash 0x9000 -
```

Prevention: don't use `restore_value: yes` on high-frequency counters or anything that updates more than a few times per hour.

## Flashing failures (can't get firmware onto the device at all)

Before assuming hardware failure:

1. **Check the USB cable** — charging-only cables lack the data lines. If the port shows up at all it's probably fine, but cheap cables have high resistance and drop voltage during flash. Use a known-good data cable.
2. **Check serial drivers** — CP2102/CH340/CH9102 all need different drivers on Windows/Mac. Install the correct one for your adapter.
3. **Reduce baud rate** — `esptool.py --baud 115200` instead of the default 921600, useful for noisy environments or long cables.
4. **Manual download mode** — hold BOOT/IO0, press and release RESET, release BOOT. The chip is now waiting for a flasher.

## When the user can't get to logs at all

Sometimes the device is so wedged that even serial output is silent. Recovery steps:

1. **Manual download mode**: hold BOOT/IO0 (or the equivalent on your board) while pressing RESET, release RESET, release BOOT. The chip is now waiting for a flasher.
2. **Erase flash**: `esptool.py --port /dev/ttyUSB0 erase_flash`. Nukes everything including the partition table; next flash needs to be a full image, not just OTA.
3. **Flash a minimal known-good config** to confirm hardware: just `esphome:`, board, `logger:`, `wifi:` AP mode. If that works, the previous config had a fatal bug.

## What to ask the user when they report a symptom

Whichever they didn't already provide:

- Exact chip and board ("ESP32-S3 N16R8 from WaveShare," not "an ESP32")
- ESPHome version
- The full YAML (with secrets redacted)
- Log output covering boot through the failure
- What changed since it last worked (a YAML change? a new HA version? a power adapter swap?)

Roughly 80% of "it broke randomly" reports turn out to be "I changed one thing yesterday."
