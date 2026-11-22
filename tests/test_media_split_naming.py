"""Tests for media split naming formats."""

from os import path as ospath


def get_split_out_path(f_path: str, file_: str, i: int, extension_first_split: bool) -> str:
    base_name, extension = ospath.splitext(file_)
    if extension_first_split:
        return f_path.replace(file_, f"{file_}.{i:03}")
    return f_path.replace(file_, f"{base_name}.part{i:03}{extension}")


def test_split_naming_default_format():
    f_path = "/downloads/movies/Avengers.mkv"
    file_ = "Avengers.mkv"
    out = get_split_out_path(f_path, file_, 1, extension_first_split=False)
    assert out == "/downloads/movies/Avengers.part001.mkv"
    out2 = get_split_out_path(f_path, file_, 12, extension_first_split=False)
    assert out2 == "/downloads/movies/Avengers.part012.mkv"


def test_split_naming_extension_first_format():
    f_path = "/downloads/movies/Avengers.mkv"
    file_ = "Avengers.mkv"
    out = get_split_out_path(f_path, file_, 1, extension_first_split=True)
    assert out == "/downloads/movies/Avengers.mkv.001"
    out2 = get_split_out_path(f_path, file_, 12, extension_first_split=True)
    assert out2 == "/downloads/movies/Avengers.mkv.012"
