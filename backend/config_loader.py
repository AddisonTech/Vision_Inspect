from pathlib import Path
import yaml

def load_input_config() -> dict:
    with open(Path(__file__).resolve().parent.parent / "configs" / "input_config.yaml", 'r') as file:
        return yaml.safe_load(file)

def load_vlm_config() -> dict:
    with open(Path(__file__).resolve().parent.parent / "configs" / "vlm_config.yaml", 'r') as file:
        return yaml.safe_load(file)

def load_inspection_config() -> dict:
    with open(Path(__file__).resolve().parent.parent / "configs" / "inspection_config.yaml", 'r') as file:
        return yaml.safe_load(file)

def load_notification_config() -> dict:
    with open(Path(__file__).resolve().parent.parent / "configs" / "notification_config.yaml", 'r') as file:
        return yaml.safe_load(file)
