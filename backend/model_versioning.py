import json
from pathlib import Path
import datetime
import logging

class ModelVersionManager:
    def __init__(self, versions_dir: Path):
        self.versions_dir = versions_dir
        versions_dir.mkdir(parents=True, exist_ok=True)

    def list_versions(self) -> list:
        versions = []
        for version_dir in sorted(self.versions_dir.iterdir()):
            if version_dir.is_dir() and (version_dir / "model_info.json").exists():
                info_path = version_dir / "model_info.json"
                with open(info_path, 'r') as f:
                    info = json.load(f)
                active = (version_dir / ".active").exists()
                versions.append({**info, "active": active})
        return versions

    def get_active_version(self):
        for version in self.list_versions():
            if version["active"]:
                return version
        return None

    def set_active_version(self, version: str) -> bool:
        for version_dir in self.versions_dir.iterdir():
            if version_dir.is_dir() and version_dir.name == version:
                (self.versions_dir / ".active").unlink(missing_ok=True)
                (version_dir / ".active").touch()
                return True
        return False

    def create_version(self, model_name: str, notes: str = "") -> dict:
        tag = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        vdir = self.versions_dir / tag
        vdir.mkdir(parents=True)
        info = {
            "version": tag,
            "model_name": model_name,
            "created_at": datetime.datetime.now().isoformat(),
            "notes": notes
        }
        with open(vdir / "model_info.json", 'w') as f:
            json.dump(info, f, indent=4)
        return info

    def rollback(self, version: str) -> bool:
        result = self.set_active_version(version)
        if result:
            logging.info(f"Rolled back to version {version}")
        else:
            logging.error(f"Failed to roll back to version {version}")
        return result

def get_version_manager() -> ModelVersionManager:
    vi_root = Path(__file__).resolve().parent.parent
    return ModelVersionManager(vi_root / "models" / "versions")
