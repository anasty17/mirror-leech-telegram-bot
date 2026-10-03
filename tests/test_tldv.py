import pytest
from bot.helper.mirror_leech_utils.download_utils.tldv_downloader import (
    caesar_decipher,
    parse_tldv_conf,
)


def test_caesar_decipher():
    # Offset of 3 (shift +3)
    # A -> D, a -> d, 0 -> 0
    assert caesar_decipher("abcXYZ012", 3) == "defABC012"
    # Offset of -3 (shift 23)
    # D -> A, d -> a, 0 -> 0
    assert caesar_decipher("defABC012", -3) == "abcXYZ012"
    # Large offset
    assert caesar_decipher("abc", 26 + 3) == "def"
    # Offset 0
    assert caesar_decipher("abcXYZ", 0) == "abcXYZ"


def test_parse_tldv_conf():
    line = "#TLDVCONF:1234567890,13,https://example.com/stream/"
    expiry, offset, base_url = parse_tldv_conf(line)
    assert expiry == "1234567890"
    assert offset == 13
    assert base_url == "https://example.com/stream/"


def test_parse_tldv_conf_malformed():
    with pytest.raises(ValueError):
        parse_tldv_conf("#NOTTLDVCONF:1,2,3")

    with pytest.raises(ValueError):
        parse_tldv_conf("#TLDVCONF:1,2")
