"""Check standalone product boundaries and literal runtime resource references."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TEXT_RESOURCES = {".gd", ".tscn", ".tres", ".gdshader", ".gdshaderinc", ".godot"}


def main():
    config = (ROOT / "project.godot").read_text(encoding="utf-8")
    war = 'config/name="积木战争"' in config
    expected = "积木战争" if war else "Block-RTS"
    assert f'config/name="{expected}"' in config, "Unknown product identity"
    forbidden = (["scripts/network", "scripts/rogue", "scripts/moba", "scripts/sandbox",
                  "scenes/main.tscn", "scenes/rogue", "scenes/moba", "data/units", "server"]
                 if war else ["scripts/block_war", "scenes/block_war", "data/block_war",
                              "assets/block_war", "assets/models/block_war", "assets/ui/block_war",
                              "assets/audio/block_war"])
    failures = []
    for name in forbidden:
        path = ROOT / name
        if path.is_file() or (path.is_dir() and any(p.is_file() for p in path.rglob("*"))):
            failures.append(f"Other product content: {name}")
    checked = 0
    paths = [ROOT / "project.godot"]
    for folder in ["scripts", "scenes", "data", "assets"]:
        paths.extend(p for p in (ROOT / folder).rglob("*") if p.suffix in TEXT_RESOURCES)
    for path in paths:
        checked += 1
        text = path.read_text(encoding="utf-8-sig")
        for match in re.finditer(r'["\']res://([^"\'\n]+)["\']', text):
            resource = match.group(1)
            # Formatted paths and directories are resolved by actual scene tests.
            if any(symbol in resource for symbol in "%{}") or resource.endswith("/"):
                continue
            if resource.startswith((".local/", "artifacts/", "builds/")):
                continue
            if not (ROOT / resource).exists():
                failures.append(f"{path.relative_to(ROOT)}: missing {resource}")
        if war and re.search(r"\b(?:RelayClient|NetworkProtocol|RogueSession|BalanceCatalog)\b", text):
            failures.append(f"RTS runtime coupling: {path.relative_to(ROOT)}")
    for failure in failures:
        print(failure)
    print(f"{expected}: {checked} runtime source files, {len(failures)} boundary/reference failures")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
