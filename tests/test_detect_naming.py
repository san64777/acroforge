from acroforge.detect.naming import name_for, slugify


def test_slugify_basic():
    assert slugify("First Name:") == "first_name"
    assert slugify("  E-mail / Address ") == "e_mail_address"
    assert slugify("") == ""


def test_name_for_uses_word_to_the_left_on_same_row():
    # words in BOTTOM-UP PDF coords: "Full" and "Name" just left of the field band [700,716]
    words = [
        {"text": "Full", "x0": 100, "x1": 128, "bottom": 701, "top": 713},
        {"text": "Name", "x0": 131, "x1": 170, "bottom": 701, "top": 713},
    ]
    rect = (180, 700, 360, 716)
    assert name_for(rect, words, fallback="text_0") == "full_name"


def test_name_for_ignores_far_away_words_and_falls_back():
    words = [{"text": "Unrelated", "x0": 100, "x1": 160, "bottom": 100, "top": 112}]  # different row
    assert name_for((180, 700, 360, 716), words, fallback="text_3") == "text_3"


def test_name_for_empty_words_falls_back():
    assert name_for((10, 10, 50, 26), [], fallback="checkbox_1") == "checkbox_1"
