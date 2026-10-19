"""Publishes the tasks to Home Assistant as entities, so they can be used on dashboards and in automations:

  sensor.home_maintenance_due           number of tasks due now, attribute `due_tasks` (names)
  binary_sensor.home_maintenance_<name>_<id>   on = due now, attributes next_due / days_until / status / last_done

These are plain state entries (no integration needed), so Home Assistant forgets them on restart; they are pushed
again every 30 minutes. A state is only sent when it changed. The event `home_maintenance_task_due` is fired by
reminders.py when a due reminder goes out."""
import re

import ha
import tasks

DUE_SENSOR = "sensor.home_maintenance_due"
_sent = {}          # entity_id -> signature of what was last pushed


def entity_id(task):
    slug = re.sub(r"[^a-z0-9]+", "_", task["name"].lower()).strip("_")[:40] or "task"
    return f"binary_sensor.home_maintenance_{slug}_{task['id']}"


def sync(on=None, force=False):
    """Pushes changed states; removes the entities of deleted tasks. Returns the number of calls made."""
    if not ha.available():
        return 0
    rows = tasks.all_rows(on)
    wanted = {DUE_SENSOR: ({"unit_of_measurement": "tasks", "friendly_name": "Home maintenance due", "icon": "mdi:home-wrench",
                            "due_tasks": [t["name"] for t in rows if t["due"]]},
                           str(sum(t["due"] for t in rows)))}
    for t in rows:
        wanted[entity_id(t)] = ({"friendly_name": t["name"], "device_class": "problem", "icon": "mdi:home-wrench",
                                 "task_id": t["id"], "next_due": t["next_due"], "days_until": t["days_until"],
                                 "status": t["status"], "last_done": t["last_done"]},
                                "on" if t["due"] else "off")
    calls = 0
    for eid, (attrs, state) in wanted.items():
        sig = (state, repr(sorted(attrs.items(), key=lambda kv: kv[0])))
        if force or _sent.get(eid) != sig:
            try:
                ha.set_state(eid, state, attrs)
                _sent[eid] = sig
                calls += 1
            except Exception as e:
                print(f"Could not publish {eid}: {e}", flush=True)
    for eid in [e for e in _sent if e not in wanted]:
        try:
            ha.remove_state(eid)
            del _sent[eid]
            calls += 1
        except Exception as e:
            print(f"Could not remove {eid}: {e}", flush=True)
    return calls
