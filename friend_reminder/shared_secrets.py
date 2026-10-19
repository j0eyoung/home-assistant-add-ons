"""Fill blank add-on options from a shared secrets file that lives only on the Green.

Looks for addon_secrets.json in the Home Assistant config folder (/homeassistant for
homeassistant_config maps, /config for config maps). An option set in the add-on's
Configuration tab always wins; only blank options are filled, and only keys the add-on knows.
"""
import json
import os

OPTIONS = "/data/options.json"
CANDIDATES = ["/homeassistant/addon_secrets.json", "/config/addon_secrets.json"]


def main():
    try:
        with open(OPTIONS) as f:
            opts = json.load(f)
    except (OSError, ValueError):
        return
    shared = {}
    for path in CANDIDATES:
        try:
            with open(path) as f:
                shared = json.load(f)
            break
        except (OSError, ValueError):
            continue
    filled = [k for k, v in shared.items() if k in opts and opts[k] in ("", None) and v not in ("", None)]
    if not filled:
        return
    for k in filled:
        opts[k] = shared[k]
    try:
        tmp = OPTIONS + ".tmp"
        with open(tmp, "w") as f:
            json.dump(opts, f)
        os.replace(tmp, OPTIONS)
        print("Filled from addon_secrets.json: " + ", ".join(sorted(filled)))
    except OSError as e:
        print(f"Could not apply addon_secrets.json: {e}")


if __name__ == "__main__":
    main()
