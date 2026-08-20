# tests/test_serialization.py

import numpy as np

from utils.serialization import make_json_serializable


def test_serializes_numpy_array():
    result = make_json_serializable(np.array([1, 2, 3]))
    assert result == [1, 2, 3]


def test_serializes_numpy_scalar():
    result = make_json_serializable(np.int32(42))
    assert result == 42
    assert isinstance(result, int)


def test_serializes_bytes():
    result = make_json_serializable(b"hello")
    assert result == "hello"


def test_serializes_nested_dict_with_numpy_values():
    data = {"a": np.float64(1.5), "b": [np.int16(2), np.int16(3)]}
    result = make_json_serializable(data)
    assert result == {"a": 1.5, "b": [2, 3]}


def test_serializes_tuple_as_list():
    result = make_json_serializable((1, 2, 3))
    assert result == [1, 2, 3]
