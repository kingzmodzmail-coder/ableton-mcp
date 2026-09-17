import pytest

from MCP_Server.dataset import consent


@pytest.fixture(autouse=True)
def isolated_consent(monkeypatch, tmp_path):
    monkeypatch.setattr(consent, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(consent, "_STATE_FILE", tmp_path / "consent.json")
    monkeypatch.setattr(consent, "_persist_failed", False)
    for name in ("ABLETON_MCP_ENABLE_DATASET", "ABLETON_MCP_DISABLE_DATASET"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("content", [None, "broken", "[]", '{"state":"unknown"}', '{"state":"unexpected"}', '{"state":[]}', '{"state":{}}'])
def test_missing_invalid_unknown_consent_disables_recording(content):
    if content is not None:
        consent._STATE_FILE.write_text(content, encoding="utf-8")
    assert not consent.recording_allowed()


def test_grant_then_withdrawal_overrides_environment(monkeypatch):
    consent.record_consent(True)
    assert consent.recording_allowed()
    monkeypatch.setenv("ABLETON_MCP_ENABLE_DATASET", "1")
    consent.record_consent(False)
    assert not consent.recording_allowed()


def test_disable_switch_wins(monkeypatch):
    consent.record_consent(True)
    monkeypatch.setenv("ABLETON_MCP_DISABLE_DATASET", "1")
    assert not consent.recording_allowed()


def test_prompting_does_not_authorize_collection():
    consent.mark_prompted()
    assert not consent.recording_allowed()


def test_training_grant_does_not_grant_telemetry(monkeypatch):
    from MCP_Server import telemetry
    monkeypatch.setattr(telemetry, "_user_consent", False)
    consent.record_consent(True)
    assert telemetry.refresh_consent_from_dataset() is False
    assert telemetry.get_telemetry_consent() is False


def test_telemetry_grant_does_not_grant_training(monkeypatch):
    from MCP_Server import telemetry
    monkeypatch.setattr(telemetry, "_user_consent", True)
    assert not consent.recording_allowed()


def test_withdrawal_blocks_queued_write():
    from unittest.mock import Mock
    from MCP_Server.dataset.recorder import SessionRecorder
    client = Mock()
    recorder = object.__new__(SessionRecorder)
    consent.record_consent(True)
    payload = {"row": {"example": "private"}}
    consent.record_consent(False)
    with pytest.raises(PermissionError):
        recorder._write_row(client, "dataset_events", payload)
    client.table.assert_not_called()


def test_external_process_withdrawal_invalidates_cached_grant():
    consent.record_consent(True)
    assert consent.recording_allowed()
    consent._STATE_FILE.write_text('{"state":"denied"}', encoding='utf-8')
    assert not consent.recording_allowed()


def test_failed_withdrawal_disables_this_process(monkeypatch):
    consent.record_consent(True)
    def fail(*args):
        raise OSError('disk failure')
    monkeypatch.setattr(consent.os, 'replace', fail)
    with pytest.raises(OSError, match='disabled'):
        consent.record_consent(False)
    assert not consent.recording_allowed()


def test_telemetry_withdrawal_strips_queued_private_fields(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from MCP_Server import telemetry
    collector = object.__new__(telemetry.TelemetryCollector)
    collector.config = SimpleNamespace(enabled=True, has_credentials=True, supabase_url='test', supabase_anon_key='test')
    monkeypatch.setattr(collector, '_is_disabled', lambda: False)
    monkeypatch.setattr(telemetry, 'HAS_SUPABASE', True)
    monkeypatch.setattr(telemetry, '_user_consent', False)
    client = Mock()
    import sys
    monkeypatch.setitem(sys.modules, 'supabase', SimpleNamespace(ClientOptions=lambda **kw: kw))
    monkeypatch.setattr(telemetry, 'create_client', lambda *a, **kw: client, raising=False)
    event = telemetry.TelemetryEvent(telemetry.EventType.TOOL_EXECUTION, 'u', 's', 1, 'v', 'test',
                                    prompt_text='private', metadata={'notes': 'private'}, error_message='private path')
    collector._send_event(event)
    data = client.table.return_value.insert.call_args.args[0]
    assert data['prompt_text'] is None and data['metadata'] == {}
    assert 'private' not in data['error_message']
