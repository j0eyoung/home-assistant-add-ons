# ESPHome external components (formerly "custom components")

**Canonical reference:** https://developers.esphome.io/architecture/components/ — when this file and the canonical docs disagree, the canonical docs win. The official guide is also more likely to be current with breaking changes.

**Starter templates:** https://github.com/esphome/starter-components — the official "copy this and adapt" templates. Recommend this over building from scratch.

## Terminology shift — read first

ESPHome **removed** the legacy `custom_component:` / "custom sensor" mechanism. The replacement is the `external_components:` system. If a user is following an old tutorial that says to drop `.h` files into `<config>/custom_components/` and reference them with `lambda` in a `custom` platform, that approach no longer compiles on current ESPHome.

The migration shape:

| Legacy (gone)                       | Modern external component                          |
| ----------------------------------- | -------------------------------------------------- |
| `.h` file in `custom_components/`   | Folder with `__init__.py`, `.h`, `.cpp`            |
| `#include "esphome.h"`              | Targeted includes (`esphome/core/component.h`, etc.) |
| Wired in via `lambda:` and `custom` platform | Wired in via `external_components:` + a real platform/component entry |
| No YAML validation                  | Schema-validated YAML                              |

Flag this on sight when reviewing user code that looks like the left column.

## Minimum file layout

```
my_components/
└── my_widget/
    ├── __init__.py        # Python: schema + codegen
    ├── my_widget.h        # C++: class declaration
    └── my_widget.cpp      # C++: implementation
```

The folder name **must match** the C++ namespace and the YAML key. ESPHome enforces this — `my_widget/` ↔ `namespace esphome::my_widget` ↔ `my_widget:` in YAML.

Referenced from the device YAML:

```yaml
external_components:
  - source:
      type: local
      path: my_components
  # or from GitHub:
  # - source: github://username/repo@branch
  #   components: [my_widget]

my_widget:
  foo: true
  bar: "hello"
```

## Python side — `__init__.py`

The Python doesn't run on the device. It runs **once on the dev machine** during `esphome compile` to validate the YAML and emit C++ code that wires the user's settings into your class.

Canonical minimal example (from the official docs):

```python
import esphome.config_validation as cv
import esphome.codegen as cg
from esphome.const import CONF_ID

CONF_FOO = "foo"
CONF_BAR = "bar"
CONF_BAZ = "baz"

example_component_ns = cg.esphome_ns.namespace("example_component")
ExampleComponent = example_component_ns.class_("ExampleComponent", cg.Component)

CONFIG_SCHEMA = cv.Schema({
    cv.GenerateID(): cv.declare_id(ExampleComponent),
    cv.Required(CONF_FOO): cv.boolean,
    cv.Optional(CONF_BAR): cv.string,
    cv.Optional(CONF_BAZ): cv.int_range(0, 255),
})

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    cg.add(var.set_foo(config[CONF_FOO]))
    if bar := config.get(CONF_BAR):
        cg.add(var.set_bar(bar))
    if baz := config.get(CONF_BAZ):
        cg.add(var.set_baz(baz))
```

Three things to internalize:

1. **`cg` = code generator.** It builds C++ for you. `cg.add(...)` emits a statement in the generated code; `cg.new_Pvariable(...)` allocates your class; `cg.register_component(...)` hooks it into the ESPHome lifecycle (so `setup()`, `loop()`, and `update()` get called).
2. **`cv` = config validation.** Built on Voluptuous. Reuse the standard validators (`cv.polling_component_schema`, `cv.GenerateID`, `cv.declare_id`, the bus-specific schemas in `i2c`/`spi`/`uart`) — don't reinvent.
3. **`to_code` must be `async`.** All ESPHome codegen is async since ~2022. Old tutorials show sync versions; those break.

## Module-level flags — frequently missed, often essential

Set as module-level variables in `__init__.py`. The canonical doc lists six:

```python
AUTO_LOAD = ["sensor"]              # auto-load these if user didn't explicitly include them
DEPENDENCIES = ["i2c"]              # fail validation if these aren't in the config
CONFLICTS_WITH = ["incompatible_component"]
CODEOWNERS = ["@yourgithubuser"]    # for PRs into core; harmless on external
MULTI_CONF = True                   # allow multiple instances of this component
# MULTI_CONF = 3                    # OR cap at a specific count
```

**`MULTI_CONF` trips up everyone.** Without it, the component can appear only once in the YAML. If your user wants two of your widgets on one device, this is the flag that enables it. When `MULTI_CONF` is set, the user's YAML uses a list:

```yaml
my_widget:
  - id: widget_one
    foo: true
  - id: widget_two
    foo: false
```

**`MULTI_CONF_NO_DEFAULT`** allows a component to be auto-loaded with zero configured instances — used by buses like `uart` that might be provided by another component (e.g. an I²C UART expander).

## `FINAL_VALIDATE_SCHEMA` — cross-component validation

`CONFIG_SCHEMA` validates the user's input in isolation. `FINAL_VALIDATE_SCHEMA` runs *after* the whole config is parsed, giving the component access to other components' settings. Use this for "I depend on UART, and I need to make sure the user actually configured `rx_pin` on that UART":

```python
def _final_validate(config):
    uart_config = fv.full_config.get()["uart"][0]
    if "rx_pin" not in uart_config:
        raise cv.Invalid("my_widget requires rx_pin on the uart")
    return config

FINAL_VALIDATE_SCHEMA = _final_validate
```

Not needed for most components, but the right tool when you need it.

## C++ side — header (canonical style)

```cpp
#pragma once

#include "esphome/core/component.h"

namespace esphome::my_widget {

class MyWidget : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;

  void set_foo(bool foo) { this->foo_ = foo; }
  void set_bar(std::string bar) { this->bar_ = bar; }
  void set_baz(int baz) { this->baz_ = baz; }

 protected:
  bool foo_{false};
  std::string bar_{};
  int baz_{0};
};

}  // namespace esphome::my_widget
```

Notes:

- **Use the C++17 nested-namespace form** `namespace esphome::my_widget { ... }`. That's what the canonical doc and recent ESPHome code use. The older `namespace esphome { namespace my_widget { ... } }` form still compiles but isn't current style.
- **Setters are typically defined inline in the header** as one-liners. ESPHome's codegen generates calls to these *before* `setup()` runs (during the autogenerated `App.register_component` flow), so they need to be cheap and side-effect-free.
- **Targeted includes only.** Pull in `esphome/core/log.h` only in the `.cpp` where you use `ESP_LOGD` etc. Never `#include "esphome.h"` — that's the deprecated umbrella header from the legacy custom-component era.
- For bus device classes: `#include "esphome/components/i2c/i2c.h"` and inherit `public i2c::I2CDevice`; same pattern for `spi::SPIDevice<...>` and `uart::UARTDevice`.

## C++ side — implementation (canonical style)

```cpp
#include "esphome/core/log.h"
#include "my_widget.h"

namespace esphome::my_widget {

static const char *TAG = "my_widget";

void MyWidget::setup() {
  // Hardware/memory initialization. Setters have already run.
}

void MyWidget::loop() {
  // Runs ~every 7ms. MUST NOT BLOCK.
}

void MyWidget::dump_config() {
  ESP_LOGCONFIG(TAG, "MyWidget:");
  ESP_LOGCONFIG(TAG, "  foo = %s", TRUEFALSE(this->foo_));
  ESP_LOGCONFIG(TAG, "  bar = %s", this->bar_.c_str());
  ESP_LOGCONFIG(TAG, "  baz = %i", this->baz_);
}

}  // namespace esphome::my_widget
```

`TAG` shows up in logs as `[my_widget]`. `dump_config` is called once at boot and again each time a log client connects.

## Lifecycle methods — the canonical guidance

In order of execution:

- **Setters** (called before `setup()`) — config values are pushed in via the generated `set_foo(...)` calls.
- **`setup()`** — once at boot. Initialize hardware, allocate buffers, perform initial bus reads. Order across components is controlled by `get_setup_priority()` (see below).
- **`loop()`** — runs approximately **every 7 ms (~7000 times per minute)**. Other components share these cycles. **Must not block.** If you need to wait, return early and check again next loop. Blocking for more than a handful of milliseconds destabilizes WiFi and can trip the watchdog.
- **`update()`** — `PollingComponent` only. Runs every `update_interval` (default 60s, user-overridable). Same non-blocking rule.
- **`dump_config()`** — called at boot and when a log client connects. **Only print values determined during `setup()`** — don't do bus reads or writes here. The canonical doc is explicit about this.

### `get_setup_priority()`

Controls the order in which components are initialized. Higher returned value → set up later. Common values in `esphome/core/component.h`:

- `setup_priority::BUS` — busses (I²C, SPI) initialize first
- `setup_priority::HARDWARE` — low-level pin/hardware setup
- `setup_priority::DATA` — typical sensors and devices (default for most)
- `setup_priority::AFTER_CONNECTION` — anything that needs WiFi/network up first
- `setup_priority::LATE` — components that should run last

```cpp
float MyWidget::get_setup_priority() const override {
  return setup_priority::DATA;
}
```

If your component reads from another component's state during `setup()`, you need to return a *lower* priority than the source (so the source initializes first, meaning it has a *higher* setup priority).

## Shutdown sequence — for graceful power-down

ESPHome distinguishes **safe shutdown** (OTA, deep sleep, requested reboot) from **forced reboot** (crash, watchdog, `App.reboot()`). Components with hardware to power down or connections to flush should implement these:

**Safe shutdown sequence (in order):**

1. `on_safe_shutdown()` — critical cleanup, runs first. Safe-shutdown only.
2. `on_shutdown()` — start the shutdown process. Send disconnect messages, stop accepting new work. Don't close connections or power down yet. **Always called when possible** (including forced reboot).
3. `teardown()` — called *repeatedly* with a timeout. Return `true` when fully done, `false` if you need more time. This is where connections actually close and buffers flush.
4. `on_powerdown()` — after all components have finished teardown. Power down hardware, sleep chips, cut power rails.

**Forced reboot:** only `on_shutdown()` runs, then the system restarts immediately.

Skeleton:

```cpp
void MyWidget::on_safe_shutdown() { /* critical-only cleanup */ }
void MyWidget::on_shutdown() { /* begin shutdown, don't fully close */ }
bool MyWidget::teardown() {
  // Return false to request more time, true when complete.
  return true;
}
void MyWidget::on_powerdown() { /* power down hardware */ }
```

Logging inside `teardown` and `on_powerdown` will likely only reach serial — network is gone by then. Keep it minimal.

Skip all of this if your component has no shutdown-critical state. A pure sensor reader doesn't need any of it.

## Exposing entities to Home Assistant

The cleanest pattern when your component has one sensor — create a `sensor.py` in the component folder:

```python
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor
from esphome.const import (
    DEVICE_CLASS_TEMPERATURE, STATE_CLASS_MEASUREMENT, UNIT_CELSIUS,
)

from . import my_widget_ns

MyTempSensor = my_widget_ns.class_("MyTempSensor", sensor.Sensor, cg.PollingComponent)

CONFIG_SCHEMA = sensor.sensor_schema(
    MyTempSensor,
    unit_of_measurement=UNIT_CELSIUS,
    accuracy_decimals=1,
    device_class=DEVICE_CLASS_TEMPERATURE,
    state_class=STATE_CLASS_MEASUREMENT,
).extend(cv.polling_component_schema("60s"))

async def to_code(config):
    var = await sensor.new_sensor(config)
    await cg.register_component(var, config)
```

Then `MyTempSensor` in C++ inherits from both `sensor::Sensor` and `PollingComponent`, and calls `this->publish_state(value);` in `update()`.

User YAML:

```yaml
sensor:
  - platform: my_widget
    name: "Living Room Temp"
```

For components that expose **multiple entities** (one widget reading temp + humidity + pressure), use the multi-entity pattern: a parent `Component` holds `sensor::Sensor *` pointers as fields, the YAML configures each as a sub-key under the parent, the Python wires them up via `sensor.new_sensor`, and the parent calls `publish_state` on each pointer. The `bme280` component is a clean reference.

## Talking to hardware — bus device classes

For each bus, inherit the device class and extend the schema:

```cpp
// header
#include "esphome/components/i2c/i2c.h"
class MyWidget : public Component, public i2c::I2CDevice { /* ... */ };
```

```python
# __init__.py
from esphome.components import i2c

CONFIG_SCHEMA = cv.Schema({ /* ... */ }).extend(i2c::i2c_device_schema(0x77))  # default addr

async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await i2c.register_i2c_device(var, config)
```

Same pattern for:
- `spi::SPIDevice<SPI_BIT_ORDER_MSB_FIRST, SPI_CLOCK_POLARITY_LOW, ...>` + `spi.spi_device_schema()` + `spi.register_spi_device`
- `uart::UARTDevice` + `uart.UART_DEVICE_SCHEMA` + `uart.register_uart_device`

The base classes provide convenience methods (`read_byte`, `write_byte`, `read_bytes`, `available`, etc.) and handle bus arbitration. Don't roll your own bus access.

For the per-bus details (GPIO, I²C, SPI, UART), see the dedicated canonical pages:
- https://developers.esphome.io/architecture/components/gpio/
- https://developers.esphome.io/architecture/components/i2c/
- https://developers.esphome.io/architecture/components/spi/
- https://developers.esphome.io/architecture/components/uart/

## Versioning is a real concern

ESPHome introduces breaking changes for external components on a roughly monthly cadence. Recent examples (as of 2026.x):

- Entity callback signatures changed to pass state by argument (2026.4)
- `TEMPLATABLE_VALUE` macro internals changed — code passing raw C++ constants to macro-generated setters may need `cg.templatable()` wrappers (2026.4)
- Climate/Fan custom mode storage moved to the entity base class (2026.4)
- `App.get_name()` returns `StringRef` instead of `std::string` (2026.4)
- `FlushResult` renamed to `UARTFlushResult` (2026.3)

When generating external-component code, **ask which ESPHome version they're targeting**, or note explicitly that the code targets current API. For long-term maintenance, point them at https://developers.esphome.io/blog/ — that's where breaking changes are announced.

## Best reference: read existing components

The fastest way to write a new component is to copy a similar one and adapt:

- Official starter templates: https://github.com/esphome/starter-components
- All in-tree components: https://github.com/esphome/esphome/tree/dev/esphome/components

Suggested templates from the in-tree set:
- Polling I²C sensor with multiple readings → `bme280`
- BLE-listener sensor → `xiaomi_lywsd03mmc` or similar `xiaomi_*`
- Climate (HVAC) device → `mitsubishi_uart`
- Switch / actuator → `gpio` switch
- Display driver → `ili9xxx` (large but canonical)

Recommend this approach explicitly to the user. Adapting a working component is dramatically less error-prone than building from scratch against rapidly evolving APIs.
