"""Gradio 검색 UI"""

from pathlib import Path
from typing import Optional

import gradio as gr

from searcher import CharacterSearcher, SearchQuery


def create_ui(data_dir: Path = Path("data"), share: bool = False) -> gr.Blocks:
    """Gradio UI 생성"""

    searcher = CharacterSearcher(data_dir=data_dir)

    def search(
        query: str,
        rating: str,
        limit: int,
    ) -> str:
        """검색 실행"""
        if not query.strip():
            return "검색어를 입력하세요."

        # 등급 필터
        rating_filter = None if rating == "전체" else rating.lower()

        search_query = SearchQuery(
            q=query,
            rating=rating_filter,
            limit=limit,
        )

        response = searcher.search(search_query)

        if response.total == 0:
            return "검색 결과가 없습니다."

        # 결과 포맷팅
        results = []
        for i, r in enumerate(response.results, 1):
            genres = ", ".join(r.genres[:3]) if r.genres else "없음"

            # desc에서 요약과 설명 추출
            summary = ""
            description = ""
            if r.desc:
                lines = r.desc.split("\n")
                for line in lines:
                    if line.startswith("요약:"):
                        summary = line[3:].strip()
                    elif line.startswith("설명:"):
                        description = line[3:].strip()


            result = f"""### [{i}] {r.name or '(이름 없음)'}
**제작자**: {r.authorname or '알 수 없음'} | **등급**: {r.content_rating.upper()} | **유사도**: {r.score:.1%}

**장르**: {genres}

**요약**: {summary or '없음'}

**설명**: {description or '없음'}

[캐릭터 페이지 열기]({r.url})

---"""
            results.append(result)

        header = f"## 검색 결과: {response.total}개\n\n"
        return header + "\n".join(results)

    # UI 구성
    with gr.Blocks(
        title="RisuRealm Search",
        theme=gr.themes.Soft(),
    ) as app:
        gr.Markdown(
            """
# RisuRealm 캐릭터 검색

RisuRealm의 캐릭터를 검색합니다. 자연어로 원하는 캐릭터를 설명해보세요.
"""
        )

        with gr.Row():
            with gr.Column(scale=4):
                query_input = gr.Textbox(
                    label="검색어",
                    placeholder="예: 판타지 세계의 얀데레 여자 캐릭터",
                    lines=1,
                )
            with gr.Column(scale=1):
                rating_input = gr.Radio(
                    label="등급",
                    choices=["전체", "SFW", "NSFW"],
                    value="전체",
                )

        with gr.Row():
            limit_input = gr.Slider(
                label="결과 수",
                minimum=5,
                maximum=50,
                value=10,
                step=5,
            )
            search_btn = gr.Button("검색", variant="primary")

        results_output = gr.Markdown(label="검색 결과")

        # 이벤트 연결
        search_btn.click(
            fn=search,
            inputs=[query_input, rating_input, limit_input],
            outputs=results_output,
        )

        query_input.submit(
            fn=search,
            inputs=[query_input, rating_input, limit_input],
            outputs=results_output,
        )

        gr.Markdown(
            """
---
*Powered by Voyage AI embeddings & ChromaDB*
"""
        )

    return app


def launch_ui(data_dir: Path = Path("data"), share: bool = False, port: int = 7860):
    """UI 실행"""
    app = create_ui(data_dir=data_dir, share=share)
    app.launch(server_name="0.0.0.0", server_port=port, share=share)
