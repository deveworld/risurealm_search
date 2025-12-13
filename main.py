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


def cmd_tag(args):
    """태깅 실행"""
    from tagger import Tagger

    tagger = Tagger(
        data_dir=args.data_dir,
        delay=args.delay,
        max_workers=args.workers,
    )
    tagger.run(count=args.count)


def cmd_index(args):
    """인덱싱 실행"""
    from searcher import ChromaIndexer

    with ChromaIndexer(data_dir=args.data_dir) as indexer:
        indexer.index_all(rebuild=args.rebuild)


def cmd_search(args):
    """검색 실행"""
    from searcher import CharacterSearcher, SearchQuery

    with CharacterSearcher(data_dir=args.data_dir) as searcher:
        query = SearchQuery(
            q=args.query,
            rating=args.rating,
            limit=args.limit,
        )
        response = searcher.search(query)

        print(f"\n검색 결과: {response.total}개\n")
        for i, result in enumerate(response.results, 1):
            print(f"[{i}] {result.name}")
            print(f"    제작자: {result.authorname}")
            print(f"    등급: {result.content_rating}, 장르: {', '.join(result.genres[:3])}")
            print(f"    요약: {result.summary or result.desc[:100]}")
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

    # tag 명령
    tag_parser = subparsers.add_parser("tag", help="LLM 태깅")
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
    elif args.command == "tag":
        cmd_tag(args)
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
