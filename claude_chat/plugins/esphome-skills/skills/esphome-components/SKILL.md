---
name: esphome-components
description: Use when working with ESPHome on ESP32, ESP32-S3/C3/C6, or ESP8266 devices — writing YAML device configurations, building external components in C++ and Python, integrating devices with Home Assistant (entities, automations, dashboards), or debugging issues like boot loops, WiFi drops, OTA failures, or flash/RAM exhaustion. Trigger this skill whenever the user mentions ESPHome, .yaml configs for ESP boards, "custom components" (now called external components), Home Assistant automations involving ESP devices, or symptoms typical of ESP firmware development. Use it even when the user only describes a hardware project ("I have a BME280 on an ESP32-C3, want to expose temperature to HA") without naming ESPHome explicitly — that workflow is exactly what this skill exists for.
---

# ESPHome Components & Home Assistant Integration

Help users design, build, and debug ESPHome firmware for ESP32 (including S3/C3/C6 variants) and ESP8266 boards, and integrate those devices cleanly with Home Assistant.

## Critical first move: identify which slice of the stack the user is in

ESPHome work splits into three layers. Diagnose which one (or which combination) the user actually needs before suggesting anything. Mis-routing a YAML-only user into C++ wastes their time; pushing a C++ developer into YAML hacks wastes everyone's.

1. **YAML device config** — sensors, switches, lights, climate, display, scripts, automations on-device, lambdas. The vast majority of ESPHome work lives here, and most "I need a custom component" requests are actually solvable with built-in platforms + lambdas. Always check this first. → `references/yaml-configs.md`

2. **External components** (formerly called "custom components") — Python + C++ that extends ESPHome to support new hardware or protocols. Required when no built-in platform fits. Note the terminology shift: ESPHome **removed** the legacy `custom_component` mechanism. Modern code uses `external_components`. If a user shows you code with `custom_component:` blocks or `#include "esphome.h"` at the top of a `.h` file, they're working from outdated docs — flag this and migrate them. → `references/external-components.md` (which routes to the canonical doc at https://developers.esphome.io/architecture/components/)

3. **Home Assistant integration** — once the device is on the network, exposing entities cleanly, building automations, lovelace dashboard cards, and using the HA API actions back to the device. → `references/home-assistant.md`

A debugging question (boot loop, OTA failing, sensor reading garbage) is its own track and may cross all three layers. → `references/debugging.md`

## Chip-specific gotchas matter and are easy to forget

ESP32, ESP32-S3, ESP32-C3, ESP32-C6, and ESP8266 are not interchangeable. Pin numbers, available peripherals, RAM budget, and even the framework (Arduino vs ESP-IDF) differ. Before generating any pin assignments or memory-sensitive code, confirm the exact board. Common traps:

- **ESP8266** has ~80 KB RAM and no Bluetooth. Big YAML configs (web_server + lots of sensors + lots of automations) will OOM at runtime, not at compile time. Symptoms look like random reboots.
- **ESP32-C3** has only one core (RISC-V) and no built-in USB-OTG on bare chips — flashing requires either an external USB-serial adapter or a board with one built in.
- **ESP32-C6** supports WiFi 6 and Thread/Zigbee but requires recent ESPHome (2024.6+) and the ESP-IDF framework (not Arduino).
- **ESP32-S3** has native USB and is the right pick for USB-HID projects.
- **GPIO 6–11 on classic ESP32** are wired to internal flash. Using them as inputs/outputs will brick the device. Strapping pins (0, 2, 5, 12, 15) need care.

The chip matters before pin numbers matter. Confirm it explicitly when the user shows you a pin assignment.

## Suggested workflow for new requests

When a user comes with a goal ("I want to read a soil moisture sensor and tell HA"), don't immediately produce a 200-line YAML config. Work through:

1. **Confirm the chip and board variant.** "ESP32" alone is ambiguous; "ESP32-WROOM-32 dev board" is specific.
2. **Check if a built-in platform already exists.** Search `esphome.io/components/` before suggesting external components. The user almost always benefits from a YAML-only solution if one is reachable.
3. **Decide which entity types to expose.** A "soil sensor" might be one `sensor` (moisture %), and maybe a `binary_sensor` (dry/wet) derived from it. Naming and `device_class` choices affect how HA renders the entity.
4. **Write the minimal YAML first**, get it compiling and reporting to HA, then layer on automations, calibration filters, deep-sleep, etc.
5. **Only drop to C++/external components when YAML genuinely can't express it** — proprietary binary protocols, timing-critical work, custom display drivers, etc.

When the user asks for "the whole thing" upfront, it's still better to deliver in layers and explain why — they'll need to debug from the minimal version anyway.

## Versioning awareness

ESPHome has a monthly-ish release cadence and **regularly introduces breaking changes for external components** (entity callback signatures, trait storage, macro internals). When generating Python or C++ for an external component, ask the user what ESPHome version they're targeting, or at minimum note that the code targets current API and may need adjustments on older/newer releases. Don't pretend stability that doesn't exist.

When in doubt about current API, the canonical references are:
- https://developers.esphome.io/architecture/components/ — component architecture guide
- https://github.com/esphome/starter-components — official starter templates
- https://github.com/esphome/esphome/tree/dev/esphome/components/ — every in-tree component as a reference implementation

Picking a similar in-tree component and reading its `__init__.py` + `.cpp` + `.h` is faster than guessing.

## When to load which reference

- User pastes YAML or asks how to wire a sensor in config → `references/yaml-configs.md`
- User wants to support a not-yet-supported chip/sensor, mentions C++, or has `__init__.py`/`.cpp`/`.h` files → `references/external-components.md`
- User asks about entities, automations, dashboards, or the device-↔-HA boundary → `references/home-assistant.md`
- User reports a symptom (boot loop, WDT reset, OTA fail, "won't connect to WiFi", "shows unavailable in HA") → `references/debugging.md`

Multiple references can apply; load them as needed.

## What this skill won't do for you

- Generate full board pin layouts without confirming the exact board variant. Pin maps for "ESP32" are wrong about a third of the time on user boards.
- Guarantee external-component code compiles against an unspecified ESPHome version. Note the assumption explicitly.
- Replace `esphome logs <device>.yaml`. When debugging, the first thing to ask for is the actual log output, not a description of the symptom.
