import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "m0032", _ROOT / "alembic/versions/0032_seed_images_cloudinary.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_moved_map_matches_bootstrap_seed():
    moved = _mod._MOVED
    seed = (_ROOT / "src/infrastructure/db/bootstrap.py").read_text(encoding="utf-8")
    assert len(moved) == 21
    for old, new in moved.items():
        assert "wikimedia.org" in old
        assert new.startswith("https://res.cloudinary.com/dv1zgaj5y/image/upload/")
        assert new in seed
        assert old not in seed
