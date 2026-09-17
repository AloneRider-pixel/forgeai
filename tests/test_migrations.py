from pathlib import Path


def test_initial_migration_exists() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0001_initial_control_plane.py"
    )
    assert migration.exists()
    assert "revision = \"0001_initial\"" in migration.read_text(encoding="utf-8")
