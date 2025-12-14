"""동의어 매핑 (한영 양방향)"""

# 한국어 -> 영어 매핑
KO_TO_EN: dict[str, list[str]] = {
    "얀데레": ["yandere"],
    "츤데레": ["tsundere"],
    "판타지": ["fantasy"],
    "로맨스": ["romance"],
    "학원": ["school", "academy"],
    "학교": ["school"],
    "고등학생": ["highschool", "학생"],
    "메이드": ["maid"],
    "집사": ["butler"],
    "뱀파이어": ["vampire"],
    "엘프": ["elf"],
    "악마": ["demon", "devil"],
    "천사": ["angel"],
    "마법사": ["mage", "wizard", "witch"],
    "기사": ["knight"],
    "공주": ["princess"],
    "왕자": ["prince"],
    "여자": ["female", "girl", "woman"],
    "여성": ["female", "woman"],
    "남자": ["male", "boy", "man"],
    "남성": ["male", "man"],
    "오빠": ["brother", "oppa"],
    "언니": ["sister", "unnie"],
    "선생님": ["teacher", "sensei"],
    "학생": ["student"],
    "로봇": ["robot", "android"],
    "인공지능": ["ai", "artificial intelligence"],
    "마녀": ["witch"],
    "요정": ["fairy"],
    "드래곤": ["dragon"],
    "용": ["dragon"],
    "늑대": ["wolf"],
    "고양이": ["cat"],
    "강아지": ["dog", "puppy"],
    "토끼": ["rabbit", "bunny"],
}

# 영어 -> 한국어 매핑
EN_TO_KO: dict[str, list[str]] = {
    "yandere": ["얀데레"],
    "tsundere": ["츤데레"],
    "fantasy": ["판타지"],
    "romance": ["로맨스"],
    "school": ["학원", "학교"],
    "academy": ["학원"],
    "highschool": ["고등학생", "고등학교"],
    "maid": ["메이드"],
    "butler": ["집사"],
    "vampire": ["뱀파이어"],
    "elf": ["엘프"],
    "demon": ["악마"],
    "devil": ["악마"],
    "angel": ["천사"],
    "mage": ["마법사"],
    "wizard": ["마법사"],
    "witch": ["마녀", "마법사"],
    "knight": ["기사"],
    "princess": ["공주"],
    "prince": ["왕자"],
    "female": ["여자", "여성"],
    "girl": ["여자", "소녀"],
    "woman": ["여자", "여성"],
    "male": ["남자", "남성"],
    "boy": ["남자", "소년"],
    "man": ["남자", "남성"],
    "brother": ["오빠", "형"],
    "sister": ["언니", "누나"],
    "teacher": ["선생님"],
    "sensei": ["선생님"],
    "student": ["학생"],
    "robot": ["로봇"],
    "android": ["로봇", "안드로이드"],
    "ai": ["인공지능"],
    "fairy": ["요정"],
    "dragon": ["드래곤", "용"],
    "wolf": ["늑대"],
    "cat": ["고양이"],
    "dog": ["강아지", "개"],
    "puppy": ["강아지"],
    "rabbit": ["토끼"],
    "bunny": ["토끼"],
}

# 통합 동의어 사전 (양방향)
SYNONYMS: dict[str, list[str]] = {**KO_TO_EN, **EN_TO_KO}


def expand_synonyms(tokens: list[str]) -> list[str]:
    """토큰 목록에 동의어를 확장하여 추가

    Args:
        tokens: 원본 토큰 목록

    Returns:
        동의어가 추가된 확장 토큰 목록
    """
    expanded = list(tokens)
    for token in tokens:
        if token in SYNONYMS:
            expanded.extend(SYNONYMS[token])
    return expanded


def get_synonym_variants(token: str) -> list[str]:
    """특정 토큰의 동의어 목록 반환 (원본 포함)

    Args:
        token: 검색할 토큰

    Returns:
        원본 토큰 + 동의어 목록
    """
    variants = [token]
    if token in SYNONYMS:
        variants.extend(SYNONYMS[token])
    return variants


def matches_with_synonyms(text: str, token: str) -> bool:
    """동의어를 포함하여 텍스트에서 토큰 매칭 확인

    Args:
        text: 검색 대상 텍스트 (소문자)
        token: 검색할 토큰 (소문자)

    Returns:
        매칭 여부
    """
    if token in text:
        return True
    if token in SYNONYMS:
        for syn in SYNONYMS[token]:
            if syn in text:
                return True
    return False
