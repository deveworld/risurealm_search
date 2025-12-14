"Gradio Search UI"

import html
import json
from pathlib import Path

import gradio as gr

from searcher import CharacterSearcher, SearchQuery


CUSTOM_CSS = """
:root {
    --font-main: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    --color-bg-page: #f9fafb;
    --color-card-bg: #ffffff;
    --color-text-main: #111827;
    --color-text-sub: #4b5563;
    --color-text-muted: #9ca3af;
    --color-primary: #4f46e5;
    --color-primary-light: #eef2ff;
    --shadow-card: 0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06);
    --shadow-card-hover: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);
    --radius-card: 16px;
    --radius-img: 12px;
}

.dark {
    --color-bg-page: #111827;
    --color-card-bg: #1f2937;
    --color-text-main: #f9fafb;
    --color-text-sub: #d1d5db;
    --color-text-muted: #6b7280;
    --color-primary: #818cf8;
    --color-primary-light: #312e81;
    --shadow-card: 0 1px 3px rgba(0,0,0,0.3);
    --shadow-card-hover: 0 10px 15px -3px rgba(0,0,0,0.4);
}

body, .gradio-container {
    font-family: var(--font-main) !important;
    background-color: var(--color-bg-page);
}

.search-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem 1rem;
}

.brand-header {
    text-align: center;
    margin-bottom: 3rem;
    animation: fadeIn 0.8s ease-out;
}

.brand-title {
    font-size: 2.5rem;
    font-weight: 700;
    color: var(--color-text-main);
    letter-spacing: -0.02em;
    margin-bottom: 0.5rem;
}

.brand-subtitle {
    font-size: 1.1rem;
    color: var(--color-text-sub);
    font-weight: 400;
}

/* Result Cards */
.result-list {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.result-card {
    background: var(--color-card-bg);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow-card);
    border: 1px solid transparent;
    padding: 1.5rem;
    display: flex;
    gap: 1.5rem;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
}

.result-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-card-hover);
    border-color: var(--color-primary-light);
}

.card-image-wrapper {
    flex-shrink: 0;
    width: 120px;
    height: 120px;
    border-radius: var(--radius-img);
    overflow: hidden;
    background-color: var(--color-bg-page);
}

.card-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.5s ease;
}

.result-card:hover .card-image {
    transform: scale(1.05);
}

.card-content {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.5rem;
}

.card-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--color-text-main);
    text-decoration: none;
    line-height: 1.4;
    margin: 0;
}

.card-title:hover {
    color: var(--color-primary);
}

.card-badges {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 0.75rem;
}

.meta-badge {
    font-size: 0.75rem;
    padding: 0.15rem 0.6rem;
    border-radius: 9999px;
    font-weight: 500;
    background-color: var(--color-bg-page);
    color: var(--color-text-sub);
}

.badge-nsfw { background-color: #fef2f2; color: #ef4444; }
.dark .badge-nsfw { background-color: #450a0a; color: #fca5a5; }

.badge-male { background-color: #eff6ff; color: #3b82f6; }
.dark .badge-male { background-color: #1e3a5f; color: #93c5fd; }

.badge-female { background-color: #fdf2f8; color: #ec4899; }
.dark .badge-female { background-color: #4a1d3d; color: #f9a8d4; }

.badge-multiple { background-color: #f5f3ff; color: #8b5cf6; }
.dark .badge-multiple { background-color: #3b2d5e; color: #c4b5fd; }

.card-description {
    font-size: 0.95rem;
    color: var(--color-text-sub);
    line-height: 1.6;
    margin-bottom: 1rem;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.card-footer {
    margin-top: auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.card-author {
    font-size: 0.85rem;
    color: var(--color-text-muted);
}

.card-link-btn {
    display: inline-flex;
    align-items: center;
    padding: 0.5rem 1rem;
    background-color: var(--color-primary-light);
    color: var(--color-primary);
    border-radius: 8px;
    font-size: 0.875rem;
    font-weight: 600;
    text-decoration: none;
    transition: background-color 0.2s;
}

.card-link-btn:hover {
    background-color: var(--color-primary);
    color: white;
}

/* Empty States */
.empty-state {
    text-align: center;
    padding: 4rem 1rem;
    color: var(--color-text-muted);
}
.empty-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
    opacity: 0.5;
}

/* Animations */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Gradio Overrides */
.block.gradio-box {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}

/* Modal */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(4px);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
}

.modal-overlay.active {
    opacity: 1;
    visibility: visible;
}

.modal-content {
    background: var(--color-card-bg);
    border-radius: var(--radius-card);
    max-width: 900px;
    width: 90%;
    max-height: 85vh;
    display: flex;
    overflow: hidden;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    transform: scale(0.9);
    transition: transform 0.3s ease;
}

.modal-overlay.active .modal-content {
    transform: scale(1);
}

.modal-image-section {
    flex: 0 0 350px;
    background: var(--color-bg-page);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 1rem;
    overflow: hidden;
}

.modal-image {
    max-width: 100%;
    max-height: 70vh;
    object-fit: contain;
    border-radius: 8px;
    background: var(--color-bg-page);
}

.modal-details {
    flex: 1;
    padding: 2rem;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    scrollbar-width: none;
    -ms-overflow-style: none;
}

.modal-details::-webkit-scrollbar {
    display: none;
}

.modal-content {
    scrollbar-width: none;
    -ms-overflow-style: none;
}

.modal-content::-webkit-scrollbar {
    display: none;
}

.modal-close {
    position: absolute;
    top: 1rem;
    right: 1rem;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--color-card-bg);
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    line-height: 1;
    padding: 0;
    padding-bottom: 3px;
    color: var(--color-text-sub);
    transition: all 0.2s;
    box-shadow: var(--shadow-card);
}

.modal-close:hover {
    background: var(--color-primary);
    color: white;
}

.modal-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-main);
    margin: 0;
}

.modal-author {
    font-size: 0.9rem;
    color: var(--color-text-muted);
}

.modal-section {
    margin-top: 0.5rem;
}

.modal-section-title {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
}

.modal-summary {
    font-size: 1rem;
    color: var(--color-text-sub);
    line-height: 1.7;
}

.modal-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}

.modal-tag {
    font-size: 0.8rem;
    padding: 0.3rem 0.75rem;
    border-radius: 9999px;
    background: var(--color-bg-page);
    color: var(--color-text-sub);
}

.modal-badges {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.modal-footer {
    margin-top: auto;
    padding-top: 1rem;
    border-top: 1px solid var(--color-bg-page);
}

.modal-link-btn {
    display: inline-flex;
    align-items: center;
    padding: 0.75rem 1.5rem;
    background-color: var(--color-primary);
    color: white;
    border-radius: 10px;
    font-size: 1rem;
    font-weight: 600;
    text-decoration: none;
    transition: all 0.2s;
}

.modal-link-btn:hover {
    background-color: var(--color-primary-light);
    color: var(--color-primary);
}

/* Card clickable area */
.result-card {
    cursor: pointer;
}

.card-link-btn {
    position: relative;
    z-index: 10;
}

/* Tablet (768px~1024px): Prevent slider overflow */
@media (min-width: 768px) and (max-width: 1024px) {
    #filter-accordion .row > div {
        min-width: 0 !important;
    }
    #filter-accordion fieldset {
        min-width: 0 !important;
    }
    #filter-accordion input[type="range"] {
        min-width: 80px !important;
    }
}

/* Mobile Responsive */
@media (max-width: 768px) {
    .search-container {
        padding: 1rem 0.5rem;
    }

    .brand-title {
        font-size: 1.8rem;
    }

    .brand-subtitle {
        font-size: 0.95rem;
    }

    .brand-header {
        margin-bottom: 1.5rem;
    }

    /* 카드 모바일 최적화 */
    .result-card {
        padding: 1rem;
        gap: 1rem;
    }

    .card-image-wrapper {
        width: 80px;
        height: 80px;
    }

    .card-title {
        font-size: 1rem;
    }

    .card-description {
        font-size: 0.85rem;
        -webkit-line-clamp: 2;
    }

    .card-author {
        font-size: 0.75rem;
    }

    .card-link-btn {
        padding: 0.4rem 0.8rem;
        font-size: 0.75rem;
    }

    .meta-badge {
        font-size: 0.65rem;
        padding: 0.1rem 0.4rem;
    }

    /* 모바일 모달 */
    .modal-content {
        flex-direction: column;
        max-height: 90vh;
        overflow-y: auto;
    }

    .modal-image-section {
        flex: 0 0 auto;
        width: 100%;
        padding: 1rem;
    }

    .modal-image {
        max-height: none;
        width: 100%;
    }

    .modal-details {
        padding: 1.5rem;
        overflow-y: visible;
    }

    .modal-title {
        font-size: 1.25rem;
    }
}
"""

CUSTOM_HEAD = """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/pretendard@5.2.5/index.min.css">
<style>
/* Mobile: Hide accordion content until JS marks it ready */
@media (max-width: 767px) {
    #filter-accordion:not(.mobile-ready) > div:not(:first-child),
    #filter-accordion:not(.mobile-ready) .wrap,
    #filter-accordion:not(.mobile-ready) .content {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        overflow: hidden !important;
    }
}
#detail-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(4px);
    z-index: 9999;
    display: none;
    align-items: center;
    justify-content: center;
}
#detail-modal.active {
    display: flex;
}
</style>
<script>
window.openCharModal = function(idx) {
    const modal = document.getElementById('detail-modal');
    const dataEl = document.getElementById('modal-data-' + idx);
    if (!modal || !dataEl) return;

    const data = JSON.parse(dataEl.dataset.modal);

    // 이미지 (절대 URL로 비교)
    const imgEl = document.getElementById('modal-img');
    const newSrc = data.img || '';
    if (!imgEl.src.endsWith(newSrc.split('/').pop())) {
        imgEl.src = newSrc;
    }

    // 텍스트 업데이트
    document.getElementById('modal-title').textContent = data.name || '이름 없음';
    document.getElementById('modal-author').textContent = 'by ' + (data.author || 'Unknown');
    document.getElementById('modal-link').href = data.url || '#';

    // 요약/설명 섹션
    const summarySection = document.getElementById('modal-summary-section');
    const descSection = document.getElementById('modal-desc-section');
    document.getElementById('modal-summary').textContent = data.summary || '';
    document.getElementById('modal-desc').textContent = data.description || '';
    summarySection.style.display = data.summary ? 'block' : 'none';
    descSection.style.display = data.description ? 'block' : 'none';
    if (!data.summary && !data.description) {
        summarySection.style.display = 'block';
        document.getElementById('modal-summary').textContent = '설명이 없습니다.';
    }

    // 뱃지
    const badgesEl = document.getElementById('modal-badges');
    badgesEl.innerHTML = data.badgesHtml || '';

    // 태그
    const tagsEl = document.getElementById('modal-tags');
    tagsEl.innerHTML = data.tagsHtml || '<span style="color:var(--color-text-muted)">태그 없음</span>';

    modal.classList.add('active');
    document.body.style.overflow = 'hidden';

    // 스크롤 초기화
    setTimeout(function() {
        document.getElementById('modal-details').scrollTop = 0;
    }, 0);
};
window.closeCharModal = function() {
    const modal = document.getElementById('detail-modal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
};
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') window.closeCharModal();
});

// Mobile Filter Auto-Collapse
(function() {
    function handleAccordion() {
        const accordion = document.querySelector("#filter-accordion");
        if (!accordion) return false;

        const toggle = accordion.querySelector(".label-wrap") ||
                       accordion.querySelector("button:first-child");
        if (!toggle) return false;

        // Mobile: close accordion, then show it
        if (window.innerWidth < 768) {
            const isOpen = toggle.classList.contains("open") ||
                           accordion.querySelector(".wrap.open") !== null;
            if (isOpen) {
                toggle.click();
            }
            // Mark as ready to remove CSS hiding
            accordion.classList.add("mobile-ready");
            return true;
        }

        // Desktop: already open, just mark as ready
        accordion.classList.add("mobile-ready");
        return true;
    }

    // Retry mechanism for Gradio's async rendering
    let attempts = 0;
    const maxAttempts = 10;

    function tryHandle() {
        attempts++;
        if (handleAccordion() || attempts >= maxAttempts) return;
        setTimeout(tryHandle, 200);
    }

    // Start ASAP
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", tryHandle);
    } else {
        tryHandle();
    }
})();
</script>
"""

MODAL_CONTAINER = """
<div id="detail-modal" onclick="if(event.target===this)closeCharModal()">
    <button class="modal-close" onclick="closeCharModal()">&times;</button>
    <div class="modal-content">
        <div class="modal-image-section">
            <img class="modal-image" id="modal-img" src="" alt="">
        </div>
        <div class="modal-details" id="modal-details">
            <div>
                <h2 class="modal-title" id="modal-title"></h2>
                <div class="modal-author" id="modal-author"></div>
            </div>
            <div class="modal-badges" id="modal-badges"></div>
            <div class="modal-section" id="modal-summary-section">
                <div class="modal-section-title">요약</div>
                <div class="modal-summary" id="modal-summary"></div>
            </div>
            <div class="modal-section" id="modal-desc-section">
                <div class="modal-section-title">설명</div>
                <div class="modal-summary" id="modal-desc"></div>
            </div>
            <div class="modal-section">
                <div class="modal-section-title">태그</div>
                <div class="modal-tags" id="modal-tags"></div>
            </div>
            <div class="modal-footer">
                <a id="modal-link" href="#" target="_blank" class="modal-link-btn">RisuRealm에서 보기</a>
            </div>
        </div>
    </div>
</div>
"""




def create_ui(data_dir: Path = Path("data"), share: bool = False) -> gr.Blocks:
    """Gradio UI 생성"""

    searcher = CharacterSearcher(data_dir=data_dir)

    def search(
        query: str,
        ratings: list[str],
        genders: list[str],
        languages: list[str],
        limit: int,
    ) -> str:
        """검색 실행"""
        if not query.strip():
            return """
            <div class="empty-state">
                <div class="empty-icon">✨</div>
                <p>무엇을 찾고 계신가요?</p>
            </div>
            """

        # 필터 로직
        all_ratings = ["sfw", "nsfw"]
        all_genders = ["female", "male", "multiple", "other"]
        all_languages = ["korean", "english", "japanese", "multilingual", "other"]

        rating_filters = [r.lower() for r in ratings] if ratings else []
        gender_filters = [g.lower() for g in genders] if genders else []
        language_filters = [lang.lower() for lang in languages] if languages else []

        if set(rating_filters) >= set(all_ratings):
            rating_filters = []
        if set(gender_filters) >= set(all_genders):
            gender_filters = []
        if set(language_filters) >= set(all_languages):
            language_filters = []

        search_query = SearchQuery(
            q=query,
            ratings=rating_filters,
            genders=gender_filters,
            languages=language_filters,
            limit=limit,
        )

        response = searcher.search(search_query)

        if response.total == 0:
            return """
            <div class="empty-state">
                <div class="empty-icon">🍃</div>
                <p>조건에 맞는 캐릭터를 찾지 못했습니다.</p>
            </div>
            """

        # 결과 렌더링
        cards = []
        for r in response.results:
            # 텍스트 처리
            summary = ""
            description = ""
            if r.desc:
                lines = r.desc.split("\n")
                has_prefix = False
                for line in lines:
                    if line.startswith("요약:"):
                        summary = line[3:].strip()
                        has_prefix = True
                    elif line.startswith("설명:"):
                        description = line[3:].strip()
                        has_prefix = True
                
                # 접두사가 하나도 없으면 전체를 설명으로 간주
                if not has_prefix:
                    description = r.desc.strip()
            
            # 요약이 있으면 요약 우선, 없으면 설명 사용
            display_text = summary if summary else description
            
            # 이미지
            img_url = f"https://sv.risuai.xyz/resource/{r.img}" if r.img else ""
            img_html = f'<img class="card-image" src="{img_url}" loading="lazy" alt="{r.name}">' if img_url else '<div style="width:100%;height:100%;background:#eee;"></div>'

            # 메타 정보
            badges = []

            # NSFW 뱃지 (SFW는 굳이 표시 안함, 깔끔함을 위해)
            if r.content_rating == "nsfw":
                badges.append('<span class="meta-badge badge-nsfw">NSFW</span>')

            # 성별 뱃지 (색상 적용)
            gender_info = {
                "female": ("여", "badge-female"),
                "male": ("남", "badge-male"),
                "multiple": ("다수", "badge-multiple"),
            }
            if r.character_gender in gender_info:
                g_label, g_class = gender_info[r.character_gender]
                badges.append(f'<span class="meta-badge {g_class}">{g_label}</span>')

            # 언어
            lang_map = {"korean": "KO", "english": "EN", "japanese": "JA", "multilingual": "Multi"}
            lang_str = lang_map.get(r.language, r.language.upper() if r.language else "")
            if lang_str:
                badges.append(f'<span class="meta-badge">{lang_str}</span>')

            badges_html = "".join(badges)
            
            # 모달용 태그 HTML 생성
            modal_badges = []
            if r.content_rating == "nsfw":
                modal_badges.append('<span class="meta-badge badge-nsfw">NSFW</span>')
            if r.language:
                lang_map = {"korean": "KO", "english": "EN", "japanese": "JA", "multilingual": "Multi"}
                lang_str = lang_map.get(r.language, r.language.upper())
                modal_badges.append(f'<span class="meta-badge">{lang_str}</span>')
            gender_info = {
                "female": ("여성", "badge-female"),
                "male": ("남성", "badge-male"),
                "multiple": ("다수", "badge-multiple"),
            }
            if r.character_gender in gender_info:
                g_label, g_class = gender_info[r.character_gender]
                modal_badges.append(f'<span class="meta-badge {g_class}">{g_label}</span>')

            tags_html_modal = "".join(f'<span class="modal-tag">{tag}</span>' for tag in (r.tags or []))

            # 모달용 데이터 (JSON)
            modal_data = {
                "name": r.name or "이름 없음",
                "author": r.authorname or "Unknown",
                "img": img_url,
                "url": r.url,
                "summary": summary,
                "description": description,
                "badgesHtml": "".join(modal_badges),
                "tagsHtml": tags_html_modal,
            }
            modal_data_json = html.escape(json.dumps(modal_data, ensure_ascii=False))
            card_idx = len(cards)

            # 카드 HTML
            card = f"""
            <div class="result-card" onclick="openCharModal({card_idx})">
                <div class="card-image-wrapper">
                    {img_html}
                </div>
                <div class="card-content">
                    <div class="card-header">
                        <span class="card-title">{r.name or '이름 없음'}</span>
                    </div>
                    <div class="card-badges">
                        {badges_html}
                    </div>
                    <div class="card-description">
                        {display_text or '설명이 없습니다.'}
                    </div>
                    <div class="card-footer">
                        <div class="card-author">by {r.authorname or 'Unknown'}</div>
                        <a href="{r.url}" target="_blank" class="card-link-btn" onclick="event.stopPropagation()">보러가기</a>
                    </div>
                </div>
            </div>
            <div id="modal-data-{card_idx}" data-modal="{modal_data_json}" style="display:none"></div>
            """
            cards.append(card)

        return f'{MODAL_CONTAINER}<div class="result-list">{"".join(cards)}</div>'

    # Gradio Blocks 구성
    with gr.Blocks(
        title="RisuRealm",
        theme=gr.themes.Base(
            primary_hue="indigo",
            radius_size="lg",
        ),
        css=CUSTOM_CSS,
        head=CUSTOM_HEAD,
    ) as app:
        
        with gr.Column(elem_classes="search-container"):
            gr.HTML("""
            <div class="brand-header">
                <div class="brand-title">RisuRealm</div>
                <div class="brand-subtitle">AI 캐릭터 검색 엔진</div>
            </div>
            """)

            with gr.Group():
                query_input = gr.Textbox(
                    label="",
                    placeholder="검색어를 입력하세요 (예: 판타지 학원 시뮬)",
                    lines=1,
                    scale=10,
                    container=False,
                    autofocus=True,
                    elem_id="search-bar"
                )
                # 검색 버튼은 제거하고 엔터키/자동완성 느낌으로 가거나, 아주 심플하게 유지
                # 여기서는 Textbox의 submit 기능 활용을 위해 버튼을 시각적으로 숨기거나 작게 배치 가능
                # 하지만 명시적인 버튼이 있는게 UX상 안전하므로 유지하되 스타일링

            with gr.Accordion("상세 필터 설정", open=True, elem_id="filter-accordion"):
                with gr.Row():
                    rating_input = gr.CheckboxGroup(
                        label="등급",
                        choices=["SFW", "NSFW"],
                        value=["SFW", "NSFW"],
                    )
                    gender_input = gr.CheckboxGroup(
                        label="성별",
                        choices=["Female", "Male", "Multiple", "Other"],
                        value=[],
                    )
                    language_input = gr.CheckboxGroup(
                        label="언어",
                        choices=["Korean", "English", "Japanese", "Multilingual", "Other"],
                        value=["Korean", "Multilingual"],
                    )
                    limit_input = gr.Slider(
                        label="표시 개수",
                        minimum=5,
                        maximum=50,
                        value=10,
                        step=5,
                    )

            results_output = gr.HTML(
                label="",
                value="""
                <div class="empty-state">
                    <div class="empty-icon">✨</div>
                    <p>검색어를 입력하여 시작하세요</p>
                </div>
                """)

        # 이벤트
        query_input.submit(
            fn=search,
            inputs=[query_input, rating_input, gender_input, language_input, limit_input],
            outputs=results_output,
        )
        
        # 필터 변경 시 자동 검색 (선택사항 - UX에 따라 다름. 여기서는 엔터 칠 때만 검색하도록 설정하여 불필요한 연산 방지)
        # 만약 필터 바꿀 때마다 검색하고 싶으면 아래 주석 해제
        # for inp in [rating_input, gender_input, language_input, limit_input]:
        #     inp.change(fn=search, inputs=[query_input, rating_input, gender_input, language_input, limit_input], outputs=results_output)

    return app


def launch_ui(data_dir: Path = Path("data"), share: bool = False, port: int = 7860):
    """UI 실행"""
    app = create_ui(data_dir=data_dir, share=share)
    app.launch(server_name="0.0.0.0", server_port=port, share=share)
