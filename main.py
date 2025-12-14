import asyncio
import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def cmd_scrape(args):
    """스크래핑 실행"""
    from scraper import RisuRealmScraper

    scraper = RisuRealmScraper(
        data_dir=args.data_dir,
        delay=args.delay,
        max_concurrent=args.concurrent,
    )
    asyncio.run(scraper.run(count=args.count))


def cmd_update(args):
    """최신 캐릭터 업데이트 (스크래핑 + 태깅 + 인덱싱)"""
    from scraper import RisuRealmScraper
    from tagger import Tagger
    from searcher import ChromaIndexer

    # 1. 새 캐릭터 스크래핑
    scraper = RisuRealmScraper(
        data_dir=args.data_dir,
        delay=args.delay,
        max_concurrent=args.concurrent,
    )
    asyncio.run(scraper.update())

    if args.scrape_only:
        return

    # 2. 새 캐릭터 태깅
    print("\n=== 태깅 시작 ===")
    tagger = Tagger(
        data_dir=args.data_dir,
        delay=0.5,
        max_workers=3,
    )
    result = tagger.run(count=0)  # 태깅 안 된 것만

    if args.no_index:
        return

    # 3. 인덱싱 (새로 태깅된 캐릭터 upsert)
    print("\n=== 인덱싱 시작 ===")
    with ChromaIndexer(data_dir=args.data_dir) as indexer:
        success_uuids = result.get("success_uuids", [])
        if success_uuids:
            # 새로 태깅 성공한 캐릭터는 upsert (기존 인덱스 업데이트 포함)
            indexer.upsert_by_uuids(success_uuids)
        else:
            # 새로 태깅된 것이 없으면 증분 인덱싱
            indexer.index_all(rebuild=False)


def cmd_full_update(args):
    """전체 캐릭터 확인 및 변경사항 업데이트"""
    import json
    from scraper import RisuRealmScraper
    from tagger import Tagger
    from searcher import ChromaIndexer

    # 1. 전체 목록 확인 및 변경된 캐릭터 재수집
    scraper = RisuRealmScraper(
        data_dir=args.data_dir,
        delay=args.delay,
        max_concurrent=args.concurrent,
    )
    changed_uuids = asyncio.run(scraper.full_update())

    if args.scrape_only:
        return

    if not changed_uuids:
        print("\n내용 변경 없음. 태깅/인덱싱 생략.")
        return

    # 2. 변경된 캐릭터 재태깅
    print("\n=== 변경된 캐릭터 재태깅 ===")

    # tagged.jsonl에서 변경된 UUID 제거
    tagged_path = args.data_dir / "tagged.jsonl"

    if tagged_path.exists():
        print(f"tagged.jsonl에서 {len(changed_uuids)}개 항목 제거 중...")
        changed_set = set(changed_uuids)

        # 변경되지 않은 항목만 유지
        kept_items = []
        with open(tagged_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    if item.get("uuid") not in changed_set:
                        kept_items.append(item)

        # 저장
        with open(tagged_path, "w", encoding="utf-8") as f:
            for item in kept_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        print(f"  유지: {len(kept_items)}개")

    # 태깅 실행
    tagger = Tagger(
        data_dir=args.data_dir,
        delay=0.5,
        max_workers=3,
    )
    tagger.run(count=0)

    if args.no_index:
        return

    # 3. 변경된 캐릭터만 인덱스 업데이트
    print("\n=== 인덱싱 시작 ===")
    with ChromaIndexer(data_dir=args.data_dir) as indexer:
        indexer.upsert_by_uuids(changed_uuids)


def cmd_tag(args):
    """태깅 실행"""
    from tagger import Tagger

    tagger = Tagger(
        data_dir=args.data_dir,
        delay=args.delay,
        max_workers=args.workers,
    )
    tagger.run(count=args.count)


def cmd_batch_tag(args):
    """배치 태깅 실행"""
    from tagger import BatchTagger

    tagger = BatchTagger(data_dir=args.data_dir, model=args.model)

    if args.action == "prepare":
        tagger.prepare_batch(limit=args.limit, skip_existing=not args.all)

    elif args.action == "start":
        if args.limit > 0 or args.all:
            tagger.prepare_batch(limit=args.limit, skip_existing=not args.all)
        tagger.upload_and_create_batch(completion_window=args.window)

    elif args.action == "status":
        status = tagger.check_status(args.batch_id)
        print(f"상태: {status['status']}")
        print(f"요청: {status['request_counts']['completed']}/{status['request_counts']['total']} 완료")
        if status['request_counts']['failed'] > 0:
            print(f"실패: {status['request_counts']['failed']}")

    elif args.action == "wait":
        tagger.wait_for_completion(args.batch_id, poll_interval=args.interval)

    elif args.action == "download":
        tagger.download_results()

    elif args.action == "process":
        tagger.process_results(replace_existing=args.all)

    elif args.action == "run":
        tagger.run_full_batch(
            limit=args.limit,
            skip_existing=not args.all,
            completion_window=args.window,
            poll_interval=args.interval,
        )


def cmd_index(args):
    """인덱싱 실행"""
    from searcher import ChromaIndexer

    with ChromaIndexer(data_dir=args.data_dir) as indexer:
        indexer.index_all(rebuild=args.rebuild)


def cmd_search(args):
    """검색 실행"""
    from searcher import CharacterSearcher, SearchQuery

    with CharacterSearcher(data_dir=args.data_dir) as searcher:
        ratings = [args.rating] if args.rating and args.rating != "all" else []
        query = SearchQuery(
            q=args.query,
            ratings=ratings,
            limit=args.limit,
        )
        response = searcher.search(query)

        print(f"\n검색 결과: {response.total}개\n")
        for i, result in enumerate(response.results, 1):
            print(f"[{i}] {result.name}")
            print(f"    제작자: {result.authorname}")
            print(f"    등급: {result.content_rating}, 태그: {', '.join(result.tags[:3])}")
            print(f"    점수: {result.score:.3f}")
            print(f"    링크: {result.url}")
            print()


def cmd_serve(args):
    """API 서버 실행"""
    import uvicorn
    from api import create_app

    app = create_app(data_dir=args.data_dir)
    uvicorn.run(app, host=args.host, port=args.port)


def cmd_ui(args):
    """Gradio UI 실행"""
    from ui import create_ui

    app = create_ui(data_dir=args.data_dir)
    app.launch(server_name="0.0.0.0", server_port=args.port, share=args.share)


def main():
    parser = argparse.ArgumentParser(description="RisuRealm 캐릭터 검색 엔진")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="데이터 저장 디렉토리",
    )

    subparsers = parser.add_subparsers(dest="command", help="실행할 명령")

    # scrape 명령
    scrape_parser = subparsers.add_parser("scrape", help="캐릭터 스크래핑")
    scrape_parser.add_argument(
        "-n", "--count",
        type=int,
        default=None,
        help="수집할 캐릭터 수 (미지정시 전체)",
    )
    scrape_parser.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="동시 요청 수",
    )
    scrape_parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="요청 간 딜레이 (초)",
    )

    # update 명령
    update_parser = subparsers.add_parser("update", help="최신 캐릭터 업데이트")
    update_parser.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="동시 요청 수",
    )
    update_parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="요청 간 딜레이 (초)",
    )
    update_parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="스크래핑만 실행 (태깅/인덱싱 생략)",
    )
    update_parser.add_argument(
        "--no-index",
        action="store_true",
        help="인덱싱 생략",
    )

    # full-update 명령
    full_update_parser = subparsers.add_parser("full-update", help="전체 캐릭터 확인 및 변경사항 업데이트")
    full_update_parser.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="동시 요청 수",
    )
    full_update_parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="요청 간 딜레이 (초)",
    )
    full_update_parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="스크래핑만 실행 (태깅/인덱싱 생략)",
    )
    full_update_parser.add_argument(
        "--no-index",
        action="store_true",
        help="인덱싱 생략",
    )

    # tag 명령
    tag_parser = subparsers.add_parser("tag", help="LLM 태깅 (실시간)")
    tag_parser.add_argument(
        "-n", "--count",
        type=int,
        default=0,
        help="태깅할 캐릭터 수 (0=전체)",
    )
    tag_parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="동시 처리 스레드 수",
    )
    tag_parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="요청 간 딜레이 (초)",
    )

    # batch-tag 명령
    batch_parser = subparsers.add_parser("batch-tag", help="Groq Batch API로 대량 태깅")
    batch_parser.add_argument(
        "action",
        choices=["prepare", "start", "status", "wait", "download", "process", "run"],
        help="실행할 작업 (run=전체 자동 실행)",
    )
    batch_parser.add_argument(
        "-n", "--limit",
        type=int,
        default=0,
        help="처리할 최대 캐릭터 수 (0=전체)",
    )
    batch_parser.add_argument(
        "--all",
        action="store_true",
        help="기존 태깅된 캐릭터도 재태깅",
    )
    batch_parser.add_argument(
        "--model",
        type=str,
        default="llama-3.3-70b-versatile",
        help="사용할 모델",
    )
    batch_parser.add_argument(
        "--window",
        type=str,
        default="24h",
        help="완료 기한 (예: 24h)",
    )
    batch_parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="상태 확인 간격 (초)",
    )
    batch_parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="배치 ID (status/wait 시 사용)",
    )

    # index 명령
    index_parser = subparsers.add_parser("index", help="벡터 인덱싱")
    index_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="기존 인덱스 삭제 후 재생성",
    )

    # search 명령
    search_parser = subparsers.add_parser("search", help="캐릭터 검색")
    search_parser.add_argument(
        "query",
        type=str,
        help="검색어",
    )
    search_parser.add_argument(
        "--rating",
        type=str,
        choices=["sfw", "nsfw", "all"],
        default=None,
        help="콘텐츠 등급 필터",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="결과 수",
    )

    # serve 명령
    serve_parser = subparsers.add_parser("serve", help="API 서버 실행")
    serve_parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="호스트 주소",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="포트 번호",
    )

    # ui 명령
    ui_parser = subparsers.add_parser("ui", help="Gradio UI 실행")
    ui_parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="포트 번호",
    )
    ui_parser.add_argument(
        "--share",
        action="store_true",
        help="Gradio 공유 링크 생성",
    )

    args = parser.parse_args()

    if args.command == "scrape":
        cmd_scrape(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "full-update":
        cmd_full_update(args)
    elif args.command == "tag":
        cmd_tag(args)
    elif args.command == "batch-tag":
        cmd_batch_tag(args)
    elif args.command == "index":
        cmd_index(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "ui":
        cmd_ui(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
