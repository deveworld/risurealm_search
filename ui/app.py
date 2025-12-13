"""Gradio 검색 UI"""

from pathlib import Path

import gradio as gr

from searcher import CharacterSearcher, SearchQuery


def create_ui(data_dir: Path = Path("data"), share: bool = False) -> gr.Blocks:
    """Gradio UI 생성"""

    searcher = CharacterSearcher(data_dir=data_dir)

    def search(
        query: str,
        ratings: list[str],
        genders: list[str],
        languages: list[str],
        genres: list[str],
        limit: int,
    ) -> str:
        """검색 실행"""
        if not query.strip():
            return "검색어를 입력하세요."

        # 필터 (체크된 항목들을 소문자로)
        rating_filters = [r.lower() for r in ratings] if ratings else []
        gender_filters = [g.lower() for g in genders] if genders else []
        language_filters = [l.lower() for l in languages] if languages else []
        genre_filters = [g.lower() for g in genres] if genres else []

        search_query = SearchQuery(
            q=query,
            ratings=rating_filters,
            genders=gender_filters,
            languages=language_filters,
            genres=genre_filters,
            limit=limit,
        )

        response = searcher.search(search_query)

        if response.total == 0:
            return "검색 결과가 없습니다."

        # 결과 포맷팅
        results = []
        for i, r in enumerate(response.results, 1):
            genres_str = ", ".join(r.genres[:3]) if r.genres else "없음"

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
**제작자**: {r.authorname or '알 수 없음'} | **등급**: {r.content_rating.upper()} | **성별**: {r.character_gender} | **유사도**: {r.score:.1%}

**장르**: {genres_str} | **언어**: {r.language}

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
            query_input = gr.Textbox(
                label="검색어",
                placeholder="예: 판타지 세계의 얀데레 여자 캐릭터",
                lines=1,
                scale=4,
            )
            search_btn = gr.Button("검색", variant="primary", scale=1)

        with gr.Row():
            with gr.Column(scale=1):
                rating_input = gr.CheckboxGroup(
                    label="등급",
                    choices=["SFW", "NSFW"],
                    value=[],
                )
            with gr.Column(scale=1):
                gender_input = gr.CheckboxGroup(
                    label="성별",
                    choices=["Female", "Male", "Multiple", "Other"],
                    value=[],
                )
            with gr.Column(scale=1):
                language_input = gr.CheckboxGroup(
                    label="언어",
                    choices=["Korean", "English", "Japanese", "Multilingual", "Chinese"],
                    value=[],
                )

        with gr.Row():
            genre_input = gr.CheckboxGroup(
                label="장르",
                choices=[
                    "Fantasy", "Modern", "Romance", "Comedy", "Dark_fantasy",
                    "School", "Simulator", "Game_original", "Scifi", "Horror",
                    "Historical", "Anime_original", "Isekai", "Adventure"
                ],
                value=[],
            )

        with gr.Row():
            limit_input = gr.Slider(
                label="결과 수",
                minimum=5,
                maximum=50,
                value=10,
                step=5,
            )

        results_output = gr.Markdown(label="검색 결과")

        # 이벤트 연결
        search_btn.click(
            fn=search,
            inputs=[query_input, rating_input, gender_input, language_input, genre_input, limit_input],
            outputs=results_output,
        )

        query_input.submit(
            fn=search,
            inputs=[query_input, rating_input, gender_input, language_input, genre_input, limit_input],
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
