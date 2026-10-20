"""Contacts file (.vcf) import: the parser and the api/import/vcf endpoint."""
import pytest

import db
import vcard

ANDROID_21 = (
    "BEGIN:VCARD\r\nVERSION:2.1\r\nN:Torres;Mike;;;\r\nFN:Mike Torres\r\n"
    "TEL;HOME:303-555-0199\r\nTEL;CELL:+1 303 555 0101\r\nEMAIL;HOME:mike@example.com\r\n"
    "BDAY:1988-03-14\r\nPHOTO;ENCODING=BASE64;JPEG:/9j/4AAQSkZJRgABAQAAAQABAAD\r\n"
    " AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\r\n AAAAAAAA==\r\n\r\nEND:VCARD\r\n"
    # quoted-printable name with a soft line break (Android export of non-ASCII names)
    "BEGIN:VCARD\r\nVERSION:2.1\r\nN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:Dupr=C3=A9;=C3=89lo=\r\ndie;;;\r\n"
    "FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:=C3=89lodie Dupr=C3=A9\r\nTEL;CELL;PREF:720-555-0144\r\nEND:VCARD\r\n"
)

GOOGLE_30 = (
    "BEGIN:VCARD\nVERSION:3.0\nFN:Ana Lopez\nN:Lopez;Ana;;;\n"
    "EMAIL;TYPE=INTERNET;TYPE=HOME:ana@example.com\nTEL;TYPE=CELL:(720) 555-0111\n"
    "BDAY:--07-02\nitem1.X-ABLabel:Old work\nCATEGORIES:myContacts\nEND:VCARD\n"
    "BEGIN:VCARD\nVERSION:3.0\nFN:Sam\\, the Plumber\nitem1.TEL:555 0199 222\nNOTE:line one\\nline two\nEND:VCARD\n"
)


def test_android_21_export_with_photo_and_cell_preference():
    by = {c["name"]: c for c in vcard.parse(ANDROID_21)}
    assert by["Mike Torres"] == {"name": "Mike Torres", "phone": "+1 303 555 0101", "email": "mike@example.com",
                                 "birthday": "1988-03-14"}


def test_quoted_printable_name_with_soft_line_break():
    names = [c["name"] for c in vcard.parse(ANDROID_21)]
    assert "Élodie Dupré" in names


def test_google_30_export_birthday_without_year_and_escaped_comma():
    by = {c["name"]: c for c in vcard.parse(GOOGLE_30)}
    assert by["Ana Lopez"]["birthday"] == "07-02" and by["Ana Lopez"]["phone"] == "(720) 555-0111"
    assert by["Sam, the Plumber"]["phone"] == "555 0199 222"          # grouped item1.TEL


def test_sorted_by_name():
    assert [c["name"] for c in vcard.parse(GOOGLE_30 + ANDROID_21)] == [
        "Ana Lopez", "Élodie Dupré", "Mike Torres", "Sam, the Plumber"]


def test_vcard_40_tel_uri_and_compact_birthdays():
    text = ("BEGIN:VCARD\nVERSION:4.0\nFN:Kai\nTEL;VALUE=uri;TYPE=\"cell,voice\":tel:+1-303-555-0177\n"
            "BDAY:19900521\nEND:VCARD\nBEGIN:VCARD\nVERSION:4.0\nFN:Lee\nBDAY:--1231\nEND:VCARD\n")
    by = {c["name"]: c for c in vcard.parse(text)}
    assert by["Kai"]["phone"] == "+1-303-555-0177" and by["Kai"]["birthday"] == "1990-05-21"
    assert by["Lee"]["birthday"] == "12-31"


def test_folded_long_name():
    text = "BEGIN:VCARD\nVERSION:3.0\nFN:Alexandra Catherine\n  Montgomery\nEND:VCARD\n"
    assert vcard.parse(text)[0]["name"] == "Alexandra Catherine Montgomery"


def test_name_from_n_when_fn_is_missing():
    text = "BEGIN:VCARD\nVERSION:2.1\nN:Reed;Sam;J;Dr.;\nTEL:555-010-0101\nEND:VCARD\n"
    assert vcard.parse(text)[0]["name"] == "Dr. Sam J Reed"


@pytest.mark.parametrize("value, params, expected", [
    ("1604-03-14", ";X-APPLE-OMIT-YEAR=1604", "03-14"),     # Apple's "no year"
    ("1990-02-29", "", "02-29"),                             # invalid with the year, fine without
    ("1992-02-29", "", "1992-02-29"),
    ("2001-13-01", "", None),
    ("soon", "", None),
    ("1985-06-01T00:00:00Z", "", "1985-06-01"),
])
def test_birthday_formats(value, params, expected):
    text = f"BEGIN:VCARD\nVERSION:3.0\nFN:X\nBDAY{params}:{value}\nEND:VCARD\n"
    assert vcard.parse(text)[0]["birthday"] == expected


def test_cards_without_a_name_and_junk_are_skipped():
    text = "hello\nBEGIN:VCARD\nVERSION:3.0\nTEL:555-010-0101\nEND:VCARD\nEND:VCARD\nFN:Loose\n"
    assert vcard.parse(text) == []


def test_exact_duplicates_in_the_file_are_listed_once():
    card = "BEGIN:VCARD\nVERSION:3.0\nFN:Mike\nTEL:303-555-0101\nEND:VCARD\n"
    assert len(vcard.parse(card * 3)) == 1


def test_long_values_are_trimmed_to_the_api_limits():
    text = f"BEGIN:VCARD\nVERSION:3.0\nFN:{'n' * 200}\nTEL:{'1' * 60}\nEMAIL:{'e' * 200}@x.com\nEND:VCARD\n"
    c = vcard.parse(text)[0]
    assert len(c["name"]) == 80 and len(c["phone"]) == 40 and len(c["email"]) == 120


# ---------------------------------------------------------------- endpoint

def test_import_lists_contacts_and_marks_the_ones_already_on_the_list(client):
    client.post("/api/friends", json={"friends": [{"name": "Someone", "phone": "303.555.0101"}]})
    r = client.post("/api/import/vcf", json={"text": ANDROID_21 + GOOGLE_30})
    assert r.status_code == 200
    by = {c["name"]: c for c in r.json()["contacts"]}
    assert by["Mike Torres"]["on_list"] is True                 # same phone number
    assert by["Ana Lopez"]["on_list"] is False
    assert len(client.get("/api/state").json()["friends"]) == 1  # nothing is saved by the import itself


def test_imported_contacts_can_be_added_with_their_birthdays(client):
    contacts = client.post("/api/import/vcf", json={"text": GOOGLE_30}).json()["contacts"]
    ana = next(c for c in contacts if c["name"] == "Ana Lopez")
    r = client.post("/api/friends", json={"friends": [{**{k: ana[k] for k in ("name", "phone", "email", "birthday")},
                                                       "tier": "close"}]})
    assert r.json()["added"] == ["Ana Lopez"]
    f = client.get("/api/state").json()["friends"][0]
    assert f["birthday"] == "07-02" and f["tier"] == "close"


def test_import_of_a_file_without_contacts_is_a_clear_error(client):
    r = client.post("/api/import/vcf", json={"text": "not a contacts file"})
    assert r.status_code == 422 and "No contacts found" in r.json()["detail"]


def test_import_accepts_a_body_over_the_normal_limit(client):
    card = "BEGIN:VCARD\nVERSION:3.0\nFN:Pat {}\nNOTE:" + "x" * 900 + "\nEND:VCARD\n"
    text = "".join(card.format(i) for i in range(1500))          # ~1.4 MB
    r = client.post("/api/import/vcf", json={"text": text})
    assert r.status_code == 200 and len(r.json()["contacts"]) == 1500


# ---------------------------------------------------------------- saving an import (Don't remind)

def _import(client, text=ANDROID_21 + GOOGLE_30):
    return {c["name"]: c for c in client.post("/api/import/vcf", json={"text": text}).json()["contacts"]}


def test_save_adds_the_chosen_and_remembers_the_rest_as_dont_remind(client):
    r = client.post("/api/import/save", json={
        "friends": [{"name": "Ana Lopez", "phone": "(720) 555-0111", "tier": "close", "birthday": "07-02"}],
        "ignore": [{"name": "Mike Torres", "phone": "+1 303 555 0101"}, {"name": "Sam, the Plumber", "phone": "555 0199 222"}],
    })
    assert r.status_code == 200
    assert r.json()["added"] == ["Ana Lopez"] and r.json()["ignored"] == 2
    by = _import(client)
    assert by["Ana Lopez"]["on_list"] is True and by["Ana Lopez"]["ignored"] is False
    assert by["Mike Torres"]["ignored"] is True and by["Mike Torres"]["on_list"] is False
    assert by["Élodie Dupré"]["ignored"] is False                                   # not in that save: still new
    assert [f["name"] for f in client.get("/api/state").json()["friends"]] == ["Ana Lopez"]


def test_dont_remind_matches_by_phone_number_not_just_the_name(client):
    client.post("/api/import/save", json={"ignore": [{"name": "Mike T", "phone": "303.555.0101"}]})
    assert _import(client)["Mike Torres"]["ignored"] is True


def test_adding_someone_on_dont_remind_takes_them_off_that_list(client):
    client.post("/api/import/save", json={"ignore": [{"name": "Mike Torres", "phone": "+1 303 555 0101"}]})
    r = client.post("/api/import/save", json={"friends": [{"name": "Mike Torres", "phone": "+1 303 555 0101", "tier": "good"}]})
    assert r.json()["added"] == ["Mike Torres"]
    mike = _import(client)["Mike Torres"]
    assert mike["on_list"] is True and mike["ignored"] is False
    assert db.rows("SELECT count(*) AS n FROM ignored")[0]["n"] == 0


def test_saving_the_same_dont_remind_twice_stores_it_once(client):
    body = {"ignore": [{"name": "Mike Torres", "phone": "+1 303 555 0101"}]}
    client.post("/api/import/save", json=body)
    assert client.post("/api/import/save", json=body).json()["ignored"] == 0
    assert db.rows("SELECT count(*) AS n FROM ignored")[0]["n"] == 1


def test_a_friend_is_never_put_on_dont_remind(client):
    client.post("/api/friends", json={"friends": [{"name": "Mike Torres", "phone": "3035550101"}]})
    assert client.post("/api/import/save", json={"ignore": [{"name": "Mike", "phone": "+1 303 555 0101"}]}).json()["ignored"] == 0


def test_saving_nothing_is_an_error(client):
    assert client.post("/api/import/save", json={}).status_code == 422


def test_a_whole_address_book_can_be_set_to_dont_remind(client):
    ignore = [{"name": f"Contact {i} " + "x" * 60, "phone": f"+1 720 555 {i:04d}"} for i in range(5000)]
    r = client.post("/api/import/save", json={"ignore": ignore})
    assert r.status_code == 200 and r.json()["ignored"] == 5000

def test_adding_by_hand_also_takes_someone_off_dont_remind(client):
    client.post("/api/import/save", json={"ignore": [{"name": "Mike Torres", "phone": "+1 303 555 0101"}]})
    client.post("/api/friends", json={"friends": [{"name": "Mike", "phone": "303-555-0101"}]})
    assert db.rows("SELECT count(*) AS n FROM ignored")[0]["n"] == 0