from MCP_Server import remote_script_install as installer


def test_force_does_not_replace_other_bridge_implementation(tmp_path):
    script = tmp_path / 'AbletonMCP' / '__init__.py'
    script.parent.mkdir()
    original = 'BRIDGE_VERSION = "1.8.0"\n'
    script.write_text(original)
    result = installer.install_remote_script(tmp_path, force=True)
    assert result[0]['status'] == 'error'
    assert script.read_text() == original


def test_repeated_install_preserves_each_backup(tmp_path, monkeypatch):
    source = tmp_path / 'source.py'
    source.write_text('SCRIPT_VERSION = "1.7.0"\n')
    monkeypatch.setattr(installer, 'bundled_remote_script_init', lambda: source)
    root = tmp_path / 'scripts'
    script = root / 'AbletonMCP' / '__init__.py'
    script.parent.mkdir(parents=True)
    script.write_text('# first custom version')
    first = installer.install_remote_script(root, force=True)[0]
    script.write_text('# second custom version')
    second = installer.install_remote_script(root, force=True)[0]
    from pathlib import Path
    assert first['backup'] != second['backup']
    assert Path(first['backup']).read_text() == '# first custom version'
    assert Path(second['backup']).read_text() == '# second custom version'
