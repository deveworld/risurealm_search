import json
from pathlib import Path
from typing import Optional


def parse_download_count(download_str: str) -> int:
    """다운로드 수 문자열을 정수로 변환

    "12.3k" -> 12300
    "1.5m" -> 1500000
    "500" -> 500
    """
    download_str = download_str.lower().strip()

    if download_str.endswith("k"):
        return int(float(download_str[:-1]) * 1000)
    elif download_str.endswith("m"):
        return int(float(download_str[:-1]) * 1000000)
    else:
        try:
            return int(download_str)
        except ValueError:
            return 0


def extract_detail(raw_data: dict, source: str) -> Optional[dict]:
    """원본 JSON에서 상세 정보 추출

    V2/V3 포맷 모두 처리
    """
    # spec 확인
    data = raw_data.get("data", raw_data)

    # 로어북 메타데이터
    character_book = data.get("character_book", {})
    lorebook_entries = character_book.get("entries", []) if character_book else []

    # 에셋 목록 (risuai extensions)
    extensions = data.get("extensions", {})
    risuai = extensions.get("risuai", {})
    additional_assets = risuai.get("additionalAssets", [])

    # V3 assets 필드
    assets = data.get("assets", [])

    asset_names = []
    if additional_assets:
        for a in additional_assets:
            if isinstance(a, list) and len(a) > 0:
                asset_names.append(a[0])
            elif isinstance(a, dict):
                asset_names.append(a.get("name", ""))
    elif assets:
        asset_names = [a.get("name", "") for a in assets if isinstance(a, dict)]

    return {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "personality": data.get("personality", ""),
        "scenario": data.get("scenario", ""),
        "first_mes": data.get("first_mes", ""),
        "alternate_greetings": data.get("alternate_greetings", []) or [],
        "system_prompt": data.get("system_prompt", "") or "",
        "post_history_instructions": data.get("post_history_instructions", "") or "",
        "tags": data.get("tags", []) or [],
        "creator": data.get("creator", "") or "",
        "creator_notes": data.get("creator_notes", "") or "",
        "character_version": data.get("character_version", "") or "",
        "has_lorebook": len(lorebook_entries) > 0,
        "lorebook_entry_count": len(lorebook_entries),
        "asset_count": len(asset_names),
        "asset_list": asset_names[:100],  # 최대 100개만 저장
    }


def save_jsonl(data: list[dict], path: Path):
    """JSONL 형식으로 저장"""
    with open(path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[dict]:
    """JSONL 파일 로드"""
    if not path.exists():
        return []

    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items


def append_jsonl(item: dict, path: Path):
    """JSONL 파일에 한 줄 추가"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


class Progress:
    """진행 상황 저장/복구"""

    def __init__(self, path: Path):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            with open(self.path, "r") as f:
                return json.load(f)
        return {
            "list_completed": False,
            "detail_completed_uuids": [],
            "detail_failed_uuids": [],
        }

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def mark_list_completed(self):
        self.data["list_completed"] = True
        self.save()

    def mark_detail_completed(self, uuid: str):
        if uuid not in self.data["detail_completed_uuids"]:
            self.data["detail_completed_uuids"].append(uuid)
            self.save()

    def mark_detail_failed(self, uuid: str):
        if uuid not in self.data["detail_failed_uuids"]:
            self.data["detail_failed_uuids"].append(uuid)
            self.save()

    def is_detail_done(self, uuid: str) -> bool:
        return uuid in self.data["detail_completed_uuids"]
