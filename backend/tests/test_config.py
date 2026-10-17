from covora.config import Settings


def test_defaults(monkeypatch):
    s = Settings(_env_file=None)
    assert s.routing_mode == "fixed"
    assert s.nemotron_nano_model == "nvidia/nemotron-nano-3-30b-a3b"
    assert s.nemotron_super_model == "nvidia/nemotron-3-super-120b-a12b"
    assert s.database_url.endswith("@localhost:5434/covora")


def test_secret_not_in_repr(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-abc123secret")
    s = Settings(_env_file=None)
    assert "nvapi-abc123secret" not in repr(s)
    assert s.secret_values() == ["nvapi-abc123secret"]


def test_memory_enabled_flag(monkeypatch):
    monkeypatch.setenv("MEMORY_ENABLED_ICP", "false")
    s = Settings(_env_file=None)
    assert s.memory_enabled("icp") is False
    assert s.memory_enabled("email") is True
