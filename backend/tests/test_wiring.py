"""The component loader: flags off = nothing loaded, a broken host never stops the backend."""

import sys
import types

import pytest
from fastapi import FastAPI

from app.modules import wiring


def _install_host(monkeypatch, name, **attrs):
    module = types.ModuleType(f"app.modules.{name}")
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, f"app.modules.{name}", module)
    return module


@pytest.fixture(autouse=True)
def _clean_loader(monkeypatch):
    monkeypatch.setattr(wiring, "_mounted", [])
    monkeypatch.setattr(wiring, "COMPONENTS", [("TEST_FLAG_A", "test_host_a"), ("TEST_FLAG_B", "test_host_b")])
    for flag in ("TEST_FLAG_A", "TEST_FLAG_B"):
        monkeypatch.delenv(flag, raising=False)


def test_lists_the_four_planned_components():
    import importlib

    real = importlib.reload(wiring).COMPONENTS
    assert real == [
        ("ENABLE_CROP_RESCUE", "crop_rescue_host"),
        ("ENABLE_FORECAST", "forecast_host"),
        ("ENABLE_ROUTE_OPTIMIZER", "routes_host"),
        ("ENABLE_VOICE_TOOLS", "voice_tools_host"),
    ]


def test_flags_off_mounts_nothing(monkeypatch):
    calls = []
    _install_host(monkeypatch, "test_host_a", mount=lambda app: calls.append("a"))
    wiring.mount_components(FastAPI())
    assert calls == []
    assert wiring._mounted == []


@pytest.mark.parametrize("value", ["false", "", "1", "yes"])
def test_only_the_word_true_switches_a_component_on(monkeypatch, value):
    calls = []
    _install_host(monkeypatch, "test_host_a", mount=lambda app: calls.append("a"))
    monkeypatch.setenv("TEST_FLAG_A", value)
    wiring.mount_components(FastAPI())
    assert calls == []


def test_flag_true_mounts_with_the_app(monkeypatch):
    app = FastAPI()
    seen = []
    _install_host(monkeypatch, "test_host_a", mount=lambda a: seen.append(a))
    monkeypatch.setenv("TEST_FLAG_A", " TRUE ")
    wiring.mount_components(app)
    assert seen == [app]


def test_missing_host_is_skipped_and_the_others_still_mount(monkeypatch, caplog):
    seen = []
    _install_host(monkeypatch, "test_host_b", mount=lambda a: seen.append("b"))
    monkeypatch.setenv("TEST_FLAG_A", "true")  # no test_host_a module exists
    monkeypatch.setenv("TEST_FLAG_B", "true")
    wiring.mount_components(FastAPI())
    assert seen == ["b"]
    assert "TEST_FLAG_A is NOT mounted" in caplog.text


def test_mount_error_is_logged_once_and_skipped(monkeypatch, caplog):
    def boom(app):
        raise RuntimeError("bad config")

    _install_host(monkeypatch, "test_host_a", mount=boom)
    monkeypatch.setenv("TEST_FLAG_A", "true")
    wiring.mount_components(FastAPI())
    assert wiring._mounted == []
    assert caplog.text.count("is NOT mounted") == 1


def test_start_and_stop_run_only_on_mounted_hosts_stop_in_reverse(monkeypatch):
    order = []
    _install_host(
        monkeypatch, "test_host_a",
        mount=lambda a: None, start=lambda: order.append("start a"), stop=lambda: order.append("stop a"),
    )
    _install_host(
        monkeypatch, "test_host_b",
        mount=lambda a: None, start=lambda: order.append("start b"), stop=lambda: order.append("stop b"),
    )
    monkeypatch.setenv("TEST_FLAG_A", "true")
    monkeypatch.setenv("TEST_FLAG_B", "true")
    wiring.mount_components(FastAPI())
    wiring.start_components()
    wiring.stop_components()
    assert order == ["start a", "start b", "stop b", "stop a"]


def test_host_without_start_stop_and_failing_start_do_not_break_the_rest(monkeypatch):
    order = []

    def bad_start():
        raise RuntimeError("nope")

    _install_host(monkeypatch, "test_host_a", mount=lambda a: None, start=bad_start)
    _install_host(monkeypatch, "test_host_b", mount=lambda a: None)  # no start/stop at all
    monkeypatch.setenv("TEST_FLAG_A", "true")
    monkeypatch.setenv("TEST_FLAG_B", "true")
    wiring.mount_components(FastAPI())
    wiring.start_components()
    wiring.stop_components()
    assert len(wiring._mounted) == 2
