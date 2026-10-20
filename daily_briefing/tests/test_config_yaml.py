"""config.yaml must pass the Supervisor's own checks, or Home Assistant silently leaves the add-on out of the store."""
import pathlib
import re

import pytest

yaml = pytest.importorskip("yaml")

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The Supervisor's schema element pattern (supervisor/addons/options.py, RE_SCHEMA_ELEMENT)
RE_SCHEMA_ELEMENT = re.compile(
    r"^(?:"
    r"|bool"
    r"|email"
    r"|url"
    r"|port"
    r"|device(?:\((?P<filter>subsystem=[a-z]+)\))?"
    r"|str(?:\((?P<s_min>\d+)?,(?P<s_max>\d+)?\))?"
    r"|password(?:\((?P<p_min>\d+)?,(?P<p_max>\d+)?\))?"
    r"|int(?:\((?P<i_min>\d+)?,(?P<i_max>\d+)?\))?"
    r"|float(?:\((?P<f_min>[\d\.]+)?,(?P<f_max>[\d\.]+)?\))?"
    r"|match\((?P<match>.*)\)"
    r"|list\((?P<list>.+)\)"
    r")\??$"
)


def load():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def test_every_schema_element_is_one_the_supervisor_accepts():
    for key, el in load()["schema"].items():
        if isinstance(el, list):            # a list option: one element type, e.g. ["str?"]
            assert len(el) == 1 and isinstance(el[0], str) and RE_SCHEMA_ELEMENT.match(el[0]), key
        else:
            assert isinstance(el, str) and RE_SCHEMA_ELEMENT.match(el), key


def test_options_and_schema_have_the_same_keys():
    c = load()
    assert set(c["options"]) == set(c["schema"])


def test_required_fields_and_images():
    c = load()
    for k in ("name", "version", "slug", "description", "arch", "image"):
        assert c.get(k), k
    assert c["slug"] == "daily_briefing" and c["image"] == "ghcr.io/j0eyoung/{arch}-ha-daily-briefing"
    assert set(c["arch"]) == {"aarch64", "amd64"}
    assert c["ingress"] is True and c["ingress_port"] == 8506 and "ports" not in c


def test_version_matches_the_changelog():
    top = re.search(r"^## (\S+)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M).group(1)
    assert load()["version"] == top
