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

    assert script.get_heads() == ["20260824a001"]

    head_rev = script.get_revision("20260824a001")
    assert head_rev is not None
    assert head_rev.down_revision == "116464527395"


def test_env_py_uses_infrastructure_metadata() -> None:
    env_path = Path(__file__).parent.parent / "alembic" / "env.py"
    source = env_path.read_text(encoding="utf-8")

    assert "from app.infrastructure.database.base import Base" in source
    assert "from app.infrastructure.database.models.user import UserModel" in source
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
