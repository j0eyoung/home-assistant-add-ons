# ESPHome YAML configuration reference

Most ESPHome work is YAML. This file covers the structure of a device config, common patterns, and the parts that bite people.

## Minimum viable config

Every ESPHome YAML needs four blocks. Without them, the device won't connect or won't be reachable:

```yaml
esphome:
  name: living-room-sensor       # lowercase, hyphens only — used as hostname
  friendly_name: Living Room Sensor

esp32:                            # or esp8266: for ESP8266 boards
  board: esp32dev                 # see https://registry.platformio.org/platforms/espressif32/boards
  framework:
    type: arduino                 # or 'esp-idf' — see notes below

logger:                           # serial + network logs
api:                              # native HA API (preferred over MQTT for HA users)
  encryption:
    key: !secret api_encryption_key
ota:
  - platform: esphome
    password: !secret ota_password
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:                             # fallback hotspot if WiFi fails
    ssid: "Living Room Fallback"
    password: !secret fallback_password

captive_portal:                   # serves a setup page when in fallback AP mode
```

`!secret` references entries in `secrets.yaml` in the same directory. Always use it for credentials — never inline them, because configs get shared.

## Framework choice: Arduino vs ESP-IDF

- **Arduino** (default on most ESPs): faster compile, more community libraries work, slightly larger binary.
- **ESP-IDF**: smaller binary, lower RAM use, better BLE stack, **required** for ESP32-C6 and for some recent features (improv-serial over USB, certain Bluetooth proxy modes).

If the user is hitting flash limits or doing BLE proxying, switching to `framework: type: esp-idf` is often the answer. It changes which third-party Arduino libraries are usable, so external components that use `<Arduino.h>` will break.

## Pin configuration

The simplest form is just a GPIO number: `pin: GPIO4` or `pin: 4`. Board aliases like `D0` (NodeMCU) map to the underlying GPIO.

Advanced pin schema for fine control:

```yaml
pin:
  number: GPIO4
  inverted: true               # invert the logic level
  mode: INPUT_PULLUP           # INPUT, OUTPUT, INPUT_PULLDOWN, OUTPUT_OPEN_DRAIN, ANALOG
  allow_other_uses: true       # suppress "already used" error when sharing a pin intentionally
  drive_strength: 20mA         # ESP32 pad current: 5mA, 10mA, 20mA, 40mA
```

`ignore_strapping_warning` and `ignore_pin_validation_error` exist to suppress specific startup warnings when you know what you're doing. Don't use them to paper over real mistakes.

## Time values

ESPHome accepts time durations in several forms anywhere a duration is expected:

```yaml
update_interval: 30s          # unit suffix: us, ms, s, min, h
update_interval: 1500ms
update_interval: '2:30'       # hours:minutes string
update_interval: never        # disable polling entirely
update_interval: 0ms          # every loop iteration (alias: always)
```

## Built-in platforms — search before you build

Before suggesting an external component, check `esphome.io/components/`. The catalog is huge. Common ones people miss:

- `bme280` / `bme680` / `bmp280` — Bosch I²C environment sensors
- `dallas` (now `one_wire` + `dallas_temp`) — DS18B20 1-wire
- `pulse_counter` / `pulse_meter` — for flow/energy meters
- `uart` + `modbus` + `modbus_controller` — covers most Modbus RTU devices in YAML alone
- `template` — synthesize any sensor/switch/binary_sensor in pure YAML with lambdas
- `homeassistant` (sensor/text_sensor/time platforms) — pull values *from* HA into the device

If you're tempted to write C++ to "read a register and publish it," `modbus_controller` or `i2c` + a `lambda` sensor usually does it.

## Anatomy of a sensor entry

```yaml
sensor:
  - platform: bme280_i2c
    address: 0x76
    temperature:
      name: "Living Room Temperature"
      id: lr_temp                          # internal id for lambdas
      device_class: temperature
      state_class: measurement             # for HA long-term statistics
      accuracy_decimals: 1
      entity_category: ""                  # "" = normal, "diagnostic", "config"
      disabled_by_default: false           # if true, user must enable in HA
      expire_after: 5min                   # mark unknown if no update within this window
      filters:                             # post-processing pipeline — see below
        - offset: -0.5
        - sliding_window_moving_average:
            window_size: 15
            send_every: 5
      on_value:
        then:
          - if:
              condition:
                lambda: 'return x > 30.0;'
              then:
                - logger.log: "Hot!"
      on_value_range:
        above: 28.0
        then:
          - logger.log: "Above threshold"
      on_raw_value:                        # fires before filters — raw hardware reading
        then:
          - logger.log:
              format: "Raw: %.1f"
              args: ['x']
    humidity:
      name: "Living Room Humidity"
    pressure:
      name: "Living Room Pressure"
    update_interval: 30s
```

Key things:

- `name:` is what HA sees. Omit it (or set `internal: true`) to keep a sensor on-device only.
- `id:` is for in-config references (lambdas, other components). Required for anything you'll reference elsewhere.
- `device_class:` and `state_class:` affect HA UX. `state_class: measurement` is needed for energy dashboard / long-term statistics on numerical readings; `state_class: total_increasing` for things like kWh meters.
- `disabled_by_default: true` means the entity exists in HA but won't show up until the user manually enables it — useful for diagnostic sensors that clutter dashboards.
- `expire_after:` marks the entity as `unknown` in HA if no value arrives within the window. Good safety net for polling sensors on unreliable connections.

## Sensor filters

Filters run in order; each receives the output of the previous. ESPHome has 27+ built-in filter types. The most useful:

**Statistical:**
```yaml
filters:
  - median:
      window_size: 7
      send_every: 4
      send_first_at: 1
  - sliding_window_moving_average:
      window_size: 15
      send_every: 5
  - exponential_moving_average:
      alpha: 0.1          # forget factor; lower = more smoothing
  - quantile:
      window_size: 7
      send_every: 4
      quantile: 0.9       # 90th percentile
```

**Throttling:**
```yaml
filters:
  - throttle: 10s                    # pass at most one value per 10s
  - throttle_average: 60s            # average values over window, send once
  - debounce: 500ms                  # wait until value stable for 500ms
  - heartbeat: 60s                   # re-publish last value every 60s regardless
  - delta: 0.5                       # only pass if value changed by ≥0.5 (absolute)
  - delta:
      min_value: 1%                  # percentage delta variant
```

**Transformation:**
```yaml
filters:
  - multiply: 0.001                  # scale raw mV reading to V
  - offset: -0.5                     # calibration offset
  - round: 1                         # round to 1 decimal place
  - clamp:
      min_value: 0.0
      max_value: 100.0
  - calibrate_linear:                # least-squares fit of measured→true pairs
      method: least_squares
      datapoints:
        - 0.0 -> 0.0
        - 500.0 -> 50.3
        - 1000.0 -> 101.1
  - lambda: 'return x * x;'         # arbitrary C++ expression
```

**Gating:**
```yaml
filters:
  - filter_out: 0.0                  # drop readings equal to this value
  - filter_out: nan                  # drop NaN readings
  - skip_initial: 3                  # ignore first 3 readings after boot
```

Order matters: calibrate first (if needed), then smooth, then throttle.

## Lambdas: the C++ escape hatch in YAML

Anywhere you see a value, you can usually substitute a C++ expression. This is how most "I need custom logic" requests get resolved without an external component:

```yaml
sensor:
  - platform: template
    name: "Dewpoint"
    lambda: |-
      const float t = id(lr_temp).state;
      const float h = id(lr_humidity).state;
      return t - ((100.0 - h) / 5.0);     // rough dewpoint
    unit_of_measurement: "°C"
    device_class: temperature
    state_class: measurement
    update_interval: 30s
```

Lambdas have full access to component IDs via `id(...)` and to ESPHome helpers (`ESP_LOGD`, `App`, etc.). They compile into the firmware. Limits:

- One-liners and short snippets only — anything beyond ~30 lines belongs in an external component for testability.
- No persistent state between invocations except via `globals:` or `static` locals in the lambda.

## Globals for persistent state

```yaml
globals:
  - id: boot_count
    type: int
    restore_value: yes
    initial_value: '0'
```

`restore_value: yes` survives reboots (stored in NVS flash). Watch out: heavy use of `restore_value` on ESP8266 wears the flash and can overflow the NVS partition. Don't do it for high-frequency counters; if NVS overflows, ESPHome will fail to restore state silently.

## Packages and substitutions

**Substitutions** — `${var}` style templating, resolved at compile time:

```yaml
substitutions:
  device_name: kitchen-temp
  update_interval: 30s
```

**Packages** — split a big YAML into reusable chunks and include them. Local files:

```yaml
packages:
  wifi: !include common/wifi.yaml
  base: !include common/device_base.yaml
```

Remote files from GitHub:

```yaml
packages:
  remote_base: github://my-org/esphome-common/base.yaml@main
```

Remote packages cannot use `!secret` — they must use `substitutions` with defaults instead.

**Merge behavior:** packages are merged non-destructively. Dictionaries merge key-by-key; lists concatenate; scalar values in the main config override package values. A substitution defined in the main file always overrides the same substitution in a package.

**`!extend`** — override a specific component from a package without rewriting the whole thing:

```yaml
packages:
  - !include common.yaml

sensor:
  - id: !extend uptime_sensor    # find the sensor with this id in the package and patch it
    update_interval: 10s
```

**`!remove`** — remove a component that a package defined:

```yaml
sensor:
  - id: !remove uptime_sensor
```

## Naming conventions that pay off

- Device hostname (`esphome.name`): `kitchen-temp`, `garage-door`, `bedroom-fan`. Hyphens, no underscores (DNS-safe).
- Entity names (`name:` on each sensor/switch): start with the room or context. HA groups by device, but raw entity_ids show up everywhere.
- Use `friendly_name` at the top so the device card in HA looks clean.

## When the user pastes you a config, look for

- Missing `api:` (means they're probably on MQTT, or about to ask why HA can't see the device)
- Inline secrets — flag this immediately, suggest `!secret`
- `update_interval` not set on polling sensors (defaults to `60s`, which surprises people)
- Use of `gpio:` numbers without confirming the board (see chip-specific gotchas in main SKILL.md)
- `restore_mode: ALWAYS_ON` etc. on switches — affects post-reboot state and is a common source of "why did my light turn on at 3am"
- `restore_value: yes` on high-frequency globals — NVS flash wear and overflow risk
