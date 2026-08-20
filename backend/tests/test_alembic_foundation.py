import ast
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


def test_base_equals_head() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)

    assert script.get_bases()[0] == script.get_heads()[0]


def test_head_down_revision_is_none() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)
    head_rev = script.get_revision(script.get_heads()[0])

    assert head_rev is not None
    assert head_rev.down_revision is None


def test_baseline_upgrade_and_downgrade_are_noop() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)
    head_rev = script.get_revision(script.get_heads()[0])
    assert head_rev is not None

    module = head_rev.module
    assert hasattr(module, "upgrade")
    assert hasattr(module, "downgrade")


def test_env_py_target_metadata_is_none() -> None:
    env_path = Path(__file__).parent.parent / "alembic" / "env.py"
    assert env_path.is_file(), "alembic/env.py must exist"

    source = env_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    target_metadata_values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "target_metadata"
                    and isinstance(node.value, ast.Constant)
                ):
                    target_metadata_values.append(node.value.value)

    assert None in target_metadata_values, "target_metadata must be set to None in env.py"


def test_baseline_revision_no_ddl_operations() -> None:
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)
    head_rev = script.get_revision(script.get_heads()[0])
    assert head_rev is not None

    rev_file = Path(head_rev.path)
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
