from app.engine.normalize import (damerau_levenshtein, days_set, email_match, fold_homoglyphs, name_match, phone_match, was_folded)


def test_fold_homoglyphs_cyrillic():
    text = "Ar***n \u041c\u0435***a"  # Cyrillic EM and IE
    assert was_folded(text)
    assert fold_homoglyphs(text) == "Ar***n Me***a"
    assert not was_folded("Ar***n Me***a")


def test_name_match_masked_and_homoglyph():
    assert name_match("Ar***n \u041c\u0435***a", "Ar***n Me***a")
    assert name_match("Pr***a Sh***a", "Pr***a Sh***a")
    assert not name_match("Ri***u Iy***r", "Su***h Iy***r")


def test_phone_and_email_match():
    assert phone_match("+91-9811XXXX01", "+91-9811XXXX01")
    assert not phone_match("+91-9844XXXX77", "+91-9844XXXX04")
    assert email_match("ar***n.m***@gmail.com", "ar***n.m***@gmail.com")
    assert not email_match("ri***u.iy***@gmail.com", "su***h.iy***@outlook.com")


def test_damerau_transposition_is_one_edit():
    assert damerau_levenshtein("84931", "84913") == 1
    assert damerau_levenshtein("84901", "84901") == 0
    assert damerau_levenshtein("84901", "11111") > 2


def test_days_set():
    assert days_set("Tue,Thu") == frozenset({"Tue", "Thu"})
    assert days_set("Sat, Sun") == frozenset({"Sat", "Sun"})
