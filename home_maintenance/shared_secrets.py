"""Fill blank add-on options from a shared secrets file that lives only on the Green.

Looks for addon_secrets.json in the Home Assistant config folder (/homeassistant for
homeassistant_config maps, /config for config maps). An option set in the add-on's
Configuration tab always wins; only blank options are filled. Everything it does is
printed to the add-on log so a missing or broken file is easy to spot.
"""
import json
import os

OPTIONS = "/data/options.json"
CANDIDATES = ["/homeassistant/addon_secrets.json", "/config/addon_secrets.json"]
# Options this add-on accepts. Home Assistant leaves optional options without a default out of
# options.json, so they have to be listed here to be filled.
KEYS = ['notify_service', 'reminder_time', 'todo_entity', 'toner_entities', 'toner_threshold', 'printer_model',
        's3_endpoint', 's3_bucket', 's3_access_key', 's3_secret_key', 's3_region', 's3_prefix']


def main():
    try:
        with open(OPTIONS) as f:
            opts = json.load(f)
    except (OSError, ValueError) as e:
        print(f"shared_secrets: cannot read {OPTIONS}: {e}")
        return
    shared = None
    found = ""
    for path in CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8-sig") as f:
                shared = json.load(f)
        except (OSError, ValueError) as e:
            print(f"shared_secrets: {path} is not valid JSON ({e}). Check for a trailing comma or a missing quote.")
            return
        found = path
        break
    if shared is None:
        print("shared_secrets: addon_secrets.json not found in " + " or ".join(CANDIDATES))
        return
    if not isinstance(shared, dict):
        print(f"shared_secrets: {found} must be a JSON object like {{\"key\": \"value\"}}")
        return
    accepted = set(KEYS) | set(opts)
    filled = [k for k, v in shared.items() if k in accepted and opts.get(k) in ("", None) and v not in ("", None)]
    if filled:
        for k in filled:
            opts[k] = shared[k]
        try:
            tmp = OPTIONS + ".tmp"
            with open(tmp, "w") as f:
                json.dump(opts, f)
            os.replace(tmp, OPTIONS)
        except OSError as e:
            print(f"shared_secrets: could not write {OPTIONS}: {e}")
            return
    print(f"shared_secrets: read {found} ({len(shared)} keys); filled {len(filled)}: " + (", ".join(sorted(filled)) or "nothing (all already set or blank)"))


if __name__ == "__main__":
    main()
