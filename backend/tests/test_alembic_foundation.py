from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_ini_exists_and_loads() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    assert ini_path.is_file(), "alembic.ini must exist in the backend directory"

    config = Config(str(ini_path))
    assert config.get_main_option("script_location") is not None


def test_script_directory_resolves() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)

    assert script is not None
    assert Path(script.dir).is_dir()


def test_single_base_revision() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)
    bases = script.get_bases()

    assert len(bases) == 1


def test_single_head_revision() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()

    assert len(heads) == 1


def test_baseline_revision_remains_root() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)

    bases = script.get_bases()
    assert bases == ["116464527395"]

    base_rev = script.get_revision("116464527395")
    assert base_rev is not None
    assert base_rev.down_revision is None


def test_auth_head_descends_from_baseline() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260829a002"]

    head_rev = script.get_revision("20260829a002")
    assert head_rev is not None
    assert head_rev.down_revision == "20260829a001"

    prev_rev = script.get_revision("20260829a001")
    assert prev_rev is not None
    assert prev_rev.down_revision == "20260824a001"

    root_prev = script.get_revision("20260824a001")
    assert root_prev is not None
    assert root_prev.down_revision == "116464527395"


def test_env_py_uses_infrastructure_metadata() -> None:
    env_path = Path(__file__).parent.parent / "alembic" / "env.py"
    source = env_path.read_text(encoding="utf-8")

    assert "from app.infrastructure.database.base import Base" in source
    assert "from app.infrastructure.database.models.user import UserModel" in source
    assert "from app.infrastructure.database.models.user_credential import UserCredentialModel" in source
    assert "RefreshSessionModel" in source
    assert "RefreshTokenModel" in source
    assert "from app.infrastructure.database.models.refresh import" in source
    assert "target_metadata = Base.metadata" in source


def test_baseline_revision_no_ddl_operations() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)
    base_rev = script.get_revision("116464527395")
    assert base_rev is not None

    rev_file = Path(base_rev.path)
    source = rev_file.read_text(encoding="utf-8")

    forbidden = [
        "op.create_table",
        "op.drop_table",
        "op.add_column",
        "op.alter_column",
        "op.create_index",
        "op.execute",
    ]
    for op in forbidden:
        assert op not in source, f"Forbidden DDL operation {op} found in baseline revision"


def _load_revision_module(rev_id: str):
    import importlib.util
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)
    rev = script.get_revision(rev_id)
    assert rev is not None, f"Revision {rev_id} must exist"

    spec = importlib.util.spec_from_file_location(f"rev_{rev_id}", rev.path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_creates_refresh_sessions_and_tokens_tables_with_exact_schema(monkeypatch) -> None:
    module = _load_revision_module("20260829a002")

    calls = []

    def fake_create_table(name, *args, **kwargs):
        calls.append((name, args, kwargs))

    import alembic.op
    monkeypatch.setattr(alembic.op, "create_table", fake_create_table)

    module.upgrade()

    assert len(calls) == 2, f"Expected 2 create_table calls, got {len(calls)}"

    # Order check
    assert calls[0][0] == "refresh_sessions"
    assert calls[1][0] == "refresh_tokens"

    # Deep schema assertions for refresh_sessions
    rs_args = calls[0][1]
    rs_cols = [arg for arg in rs_args if hasattr(arg, "name") and arg.name is not None and hasattr(arg, "type")]
    assert [c.name for c in rs_cols] == ["id", "user_id", "created_at", "absolute_expires_at", "revoked_at"]
    assert rs_cols[0].nullable is False
    assert rs_cols[1].nullable is False
    assert rs_cols[2].nullable is False
    assert rs_cols[3].nullable is False
    assert rs_cols[4].nullable is True

    # Deep schema assertions for refresh_tokens
    rt_args = calls[1][1]
    rt_cols = [arg for arg in rt_args if hasattr(arg, "name") and arg.name is not None and hasattr(arg, "type")]
    assert [c.name for c in rt_cols] == ["id", "session_id", "parent_token_id", "token_hash", "issued_at", "expires_at", "consumed_at"]
    assert rt_cols[0].nullable is False
    assert rt_cols[1].nullable is False
    assert rt_cols[2].nullable is True
    assert rt_cols[3].nullable is False
    assert rt_cols[4].nullable is False
    assert rt_cols[5].nullable is False
    assert rt_cols[6].nullable is True

    # Check for constraints
    all_elements = list(rs_args) + list(rt_args)
    constraints = [el for el in all_elements if hasattr(el, "name") and getattr(el, "name", None) is not None and not hasattr(el, "type")]
    constraint_names = sorted([c.name for c in constraints])
    expected_constraint_names = sorted([
        "pk_refresh_sessions",
        "fk_refresh_sessions_user_id_users",
        "ck_refresh_sessions_absolute_expiry",
        "pk_refresh_tokens",
        "fk_refresh_tokens_session_id_refresh_sessions",
        "fk_refresh_tokens_parent_token_id_refresh_tokens",
        "uq_refresh_tokens_token_hash",
        "uq_refresh_tokens_parent_token_id",
        "ck_refresh_tokens_hash_length",
        "ck_refresh_tokens_expiry",
    ])
    assert constraint_names == expected_constraint_names
    assert len(expected_constraint_names) == 10

    # Ensure zero ON DELETE CASCADE
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "cascade" not in source.lower()


def test_downgrade_drops_refresh_tokens_and_sessions_tables_in_reverse_order(monkeypatch) -> None:
    module = _load_revision_module("20260829a002")

    calls = []

    def fake_drop_table(name, **kwargs):
        calls.append(name)

    import alembic.op
    monkeypatch.setattr(alembic.op, "drop_table", fake_drop_table)

    module.downgrade()

    assert calls == ["refresh_tokens", "refresh_sessions"]
