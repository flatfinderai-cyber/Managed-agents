import pytest
from matching import _all_passed

def test_all_passed_empty_dict():
    # An empty dictionary of filter results should not be considered "all passed".
    assert not _all_passed({})

def test_all_passed_all_true():
    filter_results = {
        "f1": {"pass": True},
        "f2": {"pass": True}
    }
    assert _all_passed(filter_results)

def test_all_passed_some_false():
    filter_results = {
        "f1": {"pass": True},
        "f2": {"pass": False}
    }
    assert not _all_passed(filter_results)

def test_all_passed_missing_pass():
    filter_results = {
        "f1": {"pass": True},
        "f2": {}
    }
    assert not _all_passed(filter_results)

def test_all_passed_missing_some_true():
    filter_results = {
        "f1": {"pass": True},
        "f2": {"other": "value"}
    }
    assert not _all_passed(filter_results)
