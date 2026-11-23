# Home Assistant integration

ESPHome devices reach HA through one of two transports. Pick deliberately.

## Native API vs MQTT

**Native API (`api:` block)** — preferred for HA users. It's the default. The device shows up automatically once HA's ESPHome integration sees it on the network. Bidirectional, encrypted with a per-device key, supports actions, events, and the Bluetooth proxy. The device only talks to one HA instance.

**MQTT (`mqtt:` block)** — use when you don't have HA, you have multiple consumers, or you're integrating with Node-RED / other home-automation systems. Adds a broker dependency and means slightly more YAML to wire each entity to a topic.

You can technically run both at once but rarely should. When debugging "HA can't see my device," confirm which transport is active first.

## Key API config options

```yaml
api:
  encryption:
    key: !secret api_encryption_key
  reboot_timeout: 15min    # device reboots if no client connects within this window
                           # set to 0s to disable — useful for devices that run standalone
  batch_delay: 100ms       # coalesce state updates; raise if flooding HA with events
```

The `reboot_timeout` default is 15 minutes. If you deploy a device that intentionally runs without HA (e.g., display-only), set it to `0s` or the device will reboot every 15 minutes.

**API triggers:**

```yaml
api:
  on_client_connected:
    then:
      - logger.log:
          format: "HA connected from %s"
          args: ['client_info.c_str()']
  on_client_disconnected:
    then:
      - logger.log: "HA disconnected"
```

**`api.connected` condition** — useful in automations that should behave differently when HA is or isn't reachable:

```yaml
on_press:
  then:
    - if:
        condition: api.connected
        then:
          - homeassistant.action:
              action: light.toggle
              target:
                entity_id: light.bedroom
        else:
          - switch.toggle: local_relay
```

## How entities map from ESPHome to HA

Each entity in ESPHome YAML (`sensor:`, `binary_sensor:`, `switch:`, `light:`, `climate:`, etc.) with a `name:` becomes one HA entity. Entity IDs derive from the device name combined with the component name; Unicode characters in names are transliterated to ASCII (e.g., `Hálószoba` becomes `haloszoba`). Suppress an entity from HA with `internal: true` — useful for raw readings that feed a computed `template` sensor and shouldn't clutter the UI.

`device_class:` and `state_class:` are the two most underused fields. They drive:

- **Icon and unit defaults** (a `device_class: temperature` sensor gets the thermometer icon automatically)
- **Long-term statistics** in HA's Energy and Statistics dashboards — requires `state_class: measurement` for instantaneous values, `state_class: total_increasing` for monotonic counters (kWh, water liters), `state_class: total` for resettable totals
- **Energy dashboard eligibility** — only sensors with the right `device_class` (`energy`, `gas`, `water`, `power`) and `state_class` show up there

Without these, the entity still works but HA can't graph it properly. Always set them for numeric sensors.

## `homeassistant.action` — calling HA from the device

**Important:** The ESPHome integration in HA has "Allow devices to perform Home Assistant actions" **disabled by default**. The user must enable it in HA under Settings → Devices & services → ESPHome → Configure (for each device) before on-device `homeassistant.action:` calls will work.

```yaml
binary_sensor:
  - platform: gpio
    pin: GPIO0
    name: "Doorbell Button"
    on_press:
      then:
        - homeassistant.action:
            action: notify.mobile_app_my_phone
            data:
              message: "Doorbell pressed"
```

**Action responses** (ESPHome 2025.10.0+): actions can capture a response from HA:

```yaml
- homeassistant.action:
    action: input_number.get_value
    target:
      entity_id: input_number.setpoint
    capture_response: true
    response_variable: resp
    then:
      - logger.log:
          format: "Setpoint: %s"
          args: ['resp["value"].as<std::string>().c_str()']
```

Note: "Actions were previously called Services." YAML using `homeassistant.service:` still works for backward compatibility.

## Pulling state *from* HA into the device

The reverse direction — device wants to know whether the bedroom light is on, or the current outdoor temperature from HA's weather entity:

```yaml
sensor:
  - platform: homeassistant
    id: outdoor_temp
    entity_id: sensor.outdoor_temperature
    internal: true                # device-only, not re-exposed to HA

text_sensor:
  - platform: homeassistant
    id: bedroom_mode
    entity_id: input_select.bedroom_mode

binary_sensor:
  - platform: homeassistant
    id: anyone_home
    entity_id: binary_sensor.anyone_home
```

This pulls live state and updates whenever HA changes it. Useful for displays, climate setpoints derived from outdoor temp, etc.

## Automations: device vs HA — where to put them?

A common confusion. The rule of thumb:

- **On-device automation** (in ESPHome YAML, `on_press`, `on_value`, `script:`): reliable even when HA or WiFi is down. Use for **anything safety-relevant or latency-sensitive** — fire alarm cuts power, motion sensor turns on the light in the same room, doorbell triggers chime.
- **HA automation** (in HA's automation editor or YAML): use when the logic crosses multiple devices or depends on HA-only data (sun, weather, person tracking, calendars). Easier to edit without re-flashing.

A motion-triggered light in one room: on-device. A motion sensor that turns on lights only after sunset and only if no one is in "sleep" mode: HA.

## Lovelace dashboards

ESPHome devices populate HA's device registry, which means:

- The auto-generated device page in HA Settings → Devices shows all entities and lets you build a card straight from there.
- Use `entity` cards or `entities` cards for simple readouts; `gauge` for tank levels / battery; `history-graph` for sensors with `state_class: measurement`.
- The `mushroom` and `button-card` HACS frontends pair well with ESPHome's typical entity counts (one device = 5–20 entities).

ESPHome doesn't generate dashboards for you. If the user asks for "a dashboard for this device," they probably mean a YAML snippet for HA's Lovelace — that's a separate artifact, written for HA's frontend, not for the ESP.

## Bluetooth proxy

Worth flagging because it's transformative: any ESP32 (not ESP8266) can act as a Bluetooth proxy for HA, extending HA's BLE range without per-device integrations. The YAML is minimal:

```yaml
esp32_ble_tracker:
bluetooth_proxy:
  active: true     # allow HA to make outbound BLE connections via this proxy
```

The `active: true` flavor uses ~50 KB more RAM but lets HA pair with BLE devices through the proxy. On RAM-constrained boards (ESP32-C3 with many other components loaded), you may need to drop `active: true`. Requires `framework: type: esp-idf` for best results.

## Device replacement (ESPHome 2025.4.0+)

When replacing hardware, if the new device uses the same `name:` in its config and runs ESPHome 2025.4.0+, HA's ESPHome integration offers "Migrate" (preserve all settings, entity IDs, automations) or "Overwrite" (reset to defaults). Use "Migrate" to replace a failed board without breaking automations. Each device must have a **unique** name — duplicate names cause mDNS discovery failures and unexpected reconnections.

## Common HA-side surprises

- **"Unavailable" entity** after a config change: device usually disconnected during reflash, will come back. If it persists, check the ESPHome integration in HA — sometimes a device needs to be re-added after a name change.
- **Entity stuck at last value**: device crashed or lost connection but HA hasn't given up yet. Check `esphome logs` and HA's "ESPHome" integration log. You can enable log subscription in the integration options to see device logs directly in HA.
- **Renaming a device or entity**: changes the `entity_id` and breaks every automation that referenced it. Use HA's UI to rename (it preserves the `entity_id`) rather than just changing `name:` in YAML.
- **Energy dashboard doesn't show the sensor**: missing `state_class`, missing `device_class: energy`, or unit not in kWh/Wh. All three must be right.
- **`homeassistant.action` silently does nothing**: "Allow devices to perform actions" is disabled by default in the HA ESPHome integration. Enable it per-device in HA Settings → Devices & services → ESPHome → Configure.
