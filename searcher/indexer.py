"""Chroma DB 인덱싱"""

import json
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from .embedder import VoyageEmbedder


def format_document(char: dict) -> str:
    """캐릭터 정보를 검색용 문서로 변환"""
    parts = [
        f"이름: {char['name']}",
        f"제작자: {char.get('authorname', '')}",
    ]

    # LLM 태그
    llm_tags = char.get("llm_tags") or {}
    if llm_tags.get("summary"):
        parts.append(f"요약: {llm_tags['summary']}")
    if llm_tags.get("description"):
        parts.append(f"설명: {llm_tags['description']}")
    if llm_tags.get("source"):
        source_list = llm_tags["source"]
        if isinstance(source_list, list) and source_list:
            parts.append(f"원작: {', '.join(source_list)}")
        elif isinstance(source_list, str) and source_list:
            parts.append(f"원작: {source_list}")

    # 원본 태그
    if char.get("tags"):
        parts.append(f"태그: {', '.join(char['tags'])}")

    # 설명
    if char.get("desc"):
        parts.append(f"소개: {char['desc'][:500]}")

    return "\n".join(parts)


def extract_metadata(char: dict) -> dict:
    """Chroma 메타데이터 추출 (필터링용)"""
    llm_tags = char.get("llm_tags") or {}

    return {
        "uuid": char["uuid"],
        "name": char["name"],
        "authorname": char.get("authorname", ""),
        "download": char.get("download", "0"),
        "nsfw": char.get("nsfw", False),
        "content_rating": llm_tags.get("content_rating", "unknown"),
        "character_gender": llm_tags.get("character_gender", "other"),
        "language": llm_tags.get("language", "english"),
        "source": ",".join(llm_tags.get("source") or []) if isinstance(llm_tags.get("source"), list) else (llm_tags.get("source") or ""),
        "tags": ",".join(char.get("tags", [])),  # 원본 태그 사용
        "haslore": char.get("haslore", False),
        "hasAsset": char.get("hasAsset", False),
    }


class ChromaIndexer:
    """Chroma DB 인덱서"""

    COLLECTION_NAME = "risurealm_characters"

    def __init__(
        self,
        data_dir: Path = Path("data"),
        embedder: Optional[VoyageEmbedder] = None,
    ):
        self.data_dir = data_dir
        self.db_path = data_dir / "chroma_db"

        # Chroma 클라이언트 (영구 저장)
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(anonymized_telemetry=False),
        )

        # 임베딩 생성기
        self._embedder = embedder
        self._own_embedder = False

    @property
    def embedder(self) -> VoyageEmbedder:
        if self._embedder is None:
            self._embedder = VoyageEmbedder()
            self._own_embedder = True
        return self._embedder

    def get_or_create_collection(self):
        """컬렉션 가져오기 또는 생성"""
        return self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def delete_collection(self):
        """컬렉션 삭제"""
        try:
            self.client.delete_collection(self.COLLECTION_NAME)
            print(f"컬렉션 '{self.COLLECTION_NAME}' 삭제됨")
        except Exception:
            pass

    def load_tagged_data(self) -> list[dict]:
        """tagged.jsonl 로드 (UUID 중복 시 마지막 항목 사용)"""
        path = self.data_dir / "tagged.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"태그 파일이 없습니다: {path}")

        # UUID 기준 중복 제거 (마지막 항목 우선)
        char_map = {}
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    char = json.loads(line)
                    char_map[char["uuid"]] = char
        return list(char_map.values())

    def index_all(
        self,
        rebuild: bool = False,
        batch_size: int = 100,
        on_progress: Optional[callable] = None,
    ):
        """전체 캐릭터 인덱싱 (증분 지원)"""
        if rebuild:
            self.delete_collection()

        collection = self.get_or_create_collection()

        # 데이터 로드
        chars = self.load_tagged_data()

        # 증분 인덱싱: 기존 인덱스에 없는 것만 추가
        if not rebuild:
            existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()
            chars = [c for c in chars if c["uuid"] not in existing_ids]
            if not chars:
                print(f"새로 인덱싱할 캐릭터가 없습니다. (기존: {len(existing_ids)}개)")
                return len(existing_ids)
            print(f"증분 인덱싱: {len(chars)}개 새 캐릭터 (기존: {len(existing_ids)}개)")

        total = len(chars)
        print(f"총 {total}개 캐릭터 인덱싱 시작...")

        # 문서 준비
        documents = []
        metadatas = []
        ids = []

        for char in chars:
            documents.append(format_document(char))
            metadatas.append(extract_metadata(char))
            ids.append(char["uuid"])

        # 임베딩 생성
        print("임베딩 생성 중...")
        embeddings = self.embedder.embed_all(
            documents,
            on_progress=lambda done, total: print(f"  임베딩: {done}/{total}"),
            delay=0.05,
        )

        # Chroma에 추가 (배치)
        print("Chroma DB에 저장 중...")
        for i in range(0, total, batch_size):
            end = min(i + batch_size, total)
            collection.add(
                ids=ids[i:end],
                embeddings=embeddings[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end],
            )
            if on_progress:
                on_progress(end, total)
            print(f"  저장: {end}/{total}")

        print(f"인덱싱 완료: {total}개")
        return total

    def upsert_by_uuids(self, uuids: list[str], batch_size: int = 100):
        """특정 UUID들만 업데이트 (upsert)"""
        if not uuids:
            print("업데이트할 캐릭터가 없습니다.")
            return 0

        collection = self.get_or_create_collection()

        # 해당 UUID의 캐릭터만 로드
        all_chars = self.load_tagged_data()
        uuid_set = set(uuids)
        chars = [c for c in all_chars if c["uuid"] in uuid_set]

        if not chars:
            print("업데이트할 캐릭터를 찾을 수 없습니다.")
            return 0

        total = len(chars)
        print(f"{total}개 캐릭터 업데이트 중...")

        # 문서 준비
        documents = []
        metadatas = []
        ids = []

        for char in chars:
            documents.append(format_document(char))
            metadatas.append(extract_metadata(char))
            ids.append(char["uuid"])

        # 임베딩 생성
        embeddings = self.embedder.embed_all(
            documents,
            on_progress=lambda done, total: print(f"  임베딩: {done}/{total}") if done % 100 == 0 else None,
            delay=0.05,
        )

        # Chroma에 upsert (배치)
        for i in range(0, total, batch_size):
            end = min(i + batch_size, total)
            collection.upsert(
                ids=ids[i:end],
                embeddings=embeddings[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end],
            )

        print(f"업데이트 완료: {total}개")
        return total

    def close(self):
        """리소스 정리"""
        if self._own_embedder and self._embedder:
            self._embedder.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
