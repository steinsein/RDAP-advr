"""
RDAP 심화버전 (adtv1) — Streamlit 메인 앱

「종교와 사회 — 나의 시선 돌아보기」 심화버전 파일럿 테스트용 설문
"""

import random
import uuid
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from config import (
    APP_ICON,
    APP_TITLE,
    CK_ITEMS,
    CONSENT_TEXT,
    CR_SCENARIOS,
    DM_ITEMS,
    DQ_ITEMS,
    FEEDBACK_ITEMS,
    FL_ITEMS,
    PAGES,
    PAIR_LABELS,
    PART_A_INTRO,
    PART_B_INTRO,
    PART_C_INTRO,
    PART_D_INTRO,
    PART_E_INTRO,
    PROFILE_DESCRIPTIONS,
    RQ_ITEMS,
    SC_ITEMS,
    SW_SETS,
    VC_ITEMS,
    VERSION_ORDERS,
)
from scoring import (
    compute_cr_deviations,
    compute_dq_anchor,
    compute_sw_gaps,
    compute_vc_total,
    determine_profile,
    get_deviation_level,
    normalize_response,
)
from sheets_logger import log_response

# ══════════════════════════════════════════════
# 페이지 설정
# ══════════════════════════════════════════════
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════
# 모바일 친화적 CSS
# ══════════════════════════════════════════════
st.markdown("""
<style>
    /* 설문 문항 텍스트 (질문 라벨) 2배 */
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] label {
        font-size: 1.75rem !important;
        line-height: 1.6 !important;
    }
    /* 라디오 버튼 터치 영역 확대 + 선택지 텍스트 2배 */
    .stRadio > div {
        gap: 0.5rem;
    }
    .stRadio > div > label {
        padding: 0.75rem 1rem;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        cursor: pointer;
        font-size: 1.4rem !important;
        line-height: 1.6;
    }
    .stRadio > div > label p,
    .stRadio > div > label span,
    .stRadio > div > label div {
        font-size: 1.4rem !important;
    }
    .stRadio > div > label:hover {
        background-color: #f0f4f8;
    }
    /* 시나리오 텍스트 가독성 — 2배 */
    .scenario-text {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #4A90D9;
        margin-bottom: 1rem;
        font-size: 1.75rem;
        line-height: 1.7;
    }
    /* 버튼 크기 */
    .stButton > button {
        width: 100%;
        padding: 0.75rem;
        font-size: 1.3rem;
    }
    /* 안내/정보 텍스트 */
    .stMarkdown p, .stMarkdown li {
        font-size: 1.2rem;
        line-height: 1.7;
    }
    /* 결과 카드 */
    .result-card {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
    }
    /* 결과 해석 박스 */
    .result-explain {
        background-color: #f0f4f8;
        padding: 1rem 1.2rem;
        border-radius: 10px;
        margin: 0.5rem 0 1rem 0;
        line-height: 1.8;
    }
    /* 텍스트 입력 영역 글씨 크기 */
    .stTextArea textarea {
        font-size: 1.2rem !important;
        line-height: 1.6 !important;
    }
    /* 섹션 헤더 숨기기 */
    header[data-testid="stHeader"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
# 세션 초기화
# ══════════════════════════════════════════════
def init_session():
    """세션 상태 초기화."""
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.page = 0
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.responses = {}
        st.session_state.rq_responses = {}
        st.session_state.start_time = datetime.now()
        st.session_state.scores = {}
        st.session_state.data_logged = False

        # 역균형화 버전 배정
        religion_order = random.choice(["A", "B"])
        response_order = random.choice(["forward", "reverse"])
        st.session_state.version = f"{religion_order}_{response_order}"
        st.session_state.religion_order = religion_order
        st.session_state.response_order = response_order


init_session()


# ══════════════════════════════════════════════
# 유틸리티 함수
# ══════════════════════════════════════════════
def next_page():
    """다음 페이지로 이동."""
    st.session_state.page = min(st.session_state.page + 1, len(PAGES) - 1)


def show_progress():
    """설문 진행률 표시 (결과/완료 페이지 제외)."""
    if st.session_state.page < len(PAGES) - 2:  # results, submitted 제외
        progress = st.session_state.page / (len(PAGES) - 3)
        st.progress(progress)
        st.caption(f"진행률: {int(progress * 100)}%")


def save_response(item_id: str, value):
    """응답값을 세션에 저장."""
    st.session_state.responses[item_id] = value


def render_radio(item_id: str, text: str, options: list, required: bool = True) -> int | None:
    """라디오 버튼 렌더링 및 응답 반환 (0-indexed)."""
    prev = st.session_state.responses.get(item_id)
    idx = options.index(options[prev]) if prev is not None and prev < len(options) else None

    selection = st.radio(
        text,
        options=options,
        index=idx,
        key=f"radio_{item_id}",
    )
    if selection is not None:
        val = options.index(selection)
        save_response(item_id, val)
        return val
    return None


def render_text(item_id: str, text: str) -> str:
    """텍스트 입력 렌더링."""
    prev = st.session_state.responses.get(item_id, "")
    val = st.text_area(
        text,
        value=prev if isinstance(prev, str) else "",
        key=f"text_{item_id}",
    )
    save_response(item_id, val)
    return val


def get_ordered_religions(scenario_religions: list) -> list:
    """역균형화 버전에 따라 종교 순서 반환."""
    full_order = VERSION_ORDERS[st.session_state.religion_order]
    # 시나리오에 포함된 종교만 필터링하되 순서 유지
    return [r for r in full_order if r in scenario_religions]


def get_options(options: list, scenario: dict | None = None,
                religion: str | None = None) -> list:
    """응답 선택지를 역균형화하여 반환."""
    opts = options.copy()

    # NR-A 특수 선택지 교체
    if religion == "NR-A" and scenario and "options_NR_A_override" in scenario:
        for idx, replacement in scenario["options_NR_A_override"].items():
            opts[idx] = replacement

    # 역방향이면 선택지 순서 역전
    if st.session_state.response_order == "reverse":
        opts = opts[::-1]

    return opts


# ══════════════════════════════════════════════
# 페이지 렌더링 함수
# ══════════════════════════════════════════════
def render_consent():
    """블록 0: 동의 및 선별."""
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.markdown("---")
    st.markdown(CONSENT_TEXT)
    st.markdown("---")

    can_proceed = True
    for item in SC_ITEMS:
        prev = st.session_state.responses.get(item["id"])
        idx = prev if prev is not None else None
        sel = st.radio(
            item["text"],
            options=item["options"],
            index=idx,
            key=f"sc_{item['id']}",
        )
        if sel is not None:
            val = item["options"].index(sel)
            save_response(item["id"], val)
            if item.get("gate") and val != 0:
                can_proceed = False

    if not can_proceed:
        st.warning("참여 조건을 충족하지 않아 설문을 진행할 수 없습니다. 감사합니다.")
        return

    # 모든 항목 응답 확인
    all_answered = all(
        st.session_state.responses.get(item["id"]) is not None
        for item in SC_ITEMS
    )
    if all_answered and can_proceed:
        st.button("다음으로", on_click=next_page, type="primary")


def render_demographics():
    """블록 1: 인구통계."""
    show_progress()
    st.subheader("기본 정보")
    st.markdown("먼저 몇 가지 기본 정보를 여쭤보겠습니다.")
    st.markdown("---")

    for item in DM_ITEMS:
        render_radio(item["id"], item["text"], item["options"])
        st.markdown("")

    all_answered = all(
        st.session_state.responses.get(item["id"]) is not None
        for item in DM_ITEMS
    )
    if all_answered:
        st.button("다음으로", on_click=next_page, type="primary")
    else:
        st.info("모든 문항에 응답해 주세요.")


def render_part_a():
    """파트 A: 직접 질문 (DQ)."""
    show_progress()
    st.subheader("파트 A. 종교와 관련된 일반적인 생각")
    st.markdown(PART_A_INTRO)
    st.markdown("---")

    for item in DQ_ITEMS:
        opts = get_options(item["options"])
        render_radio(item["id"], item["text"], opts)
        st.markdown("")

    all_answered = all(
        st.session_state.responses.get(item["id"]) is not None
        for item in DQ_ITEMS
    )
    if all_answered:
        st.button("다음으로", on_click=next_page, type="primary")
    else:
        st.info("모든 문항에 응답해 주세요.")


def render_part_b():
    """파트 B: 비교 응답 (CR) + 방해 문항 (FL)."""
    show_progress()
    st.subheader("파트 B. 일상 상황")
    st.markdown(PART_B_INTRO)
    st.markdown("---")

    all_ids = []

    for scenario in CR_SCENARIOS:
        st.markdown(f"#### {scenario['title']}")

        ordered_religions = get_ordered_religions(scenario["religions"])

        for rel in ordered_religions:
            item_id = scenario["item_ids"][rel]
            all_ids.append(item_id)

            # 시나리오 텍스트 생성
            if "desc" in scenario:
                text = scenario["template"].format(
                    desc=scenario["desc"][rel],
                    example=scenario["examples"][rel],
                )
            else:
                text = scenario["template"].format(example=scenario["examples"][rel])

            st.markdown(f'<div class="scenario-text">{text}</div>', unsafe_allow_html=True)
            opts = get_options(scenario["options"], scenario, rel)
            render_radio(item_id, "응답을 선택해 주세요.", opts)
            st.markdown("")

        st.markdown("---")

        # 해당 시나리오 뒤에 방해 문항 삽입
        for fl in FL_ITEMS:
            if fl["insert_after_scenario"] == scenario["id"]:
                all_ids.append(fl["id"])
                render_radio(fl["id"], fl["text"], fl["options"])
                st.markdown("---")

    all_answered = all(
        st.session_state.responses.get(iid) is not None
        for iid in all_ids
    )
    if all_answered:
        st.button("다음으로", on_click=next_page, type="primary")
    else:
        st.info("모든 문항에 응답해 주세요.")


def render_part_c():
    """파트 C: 당위-실제 (SW)."""
    show_progress()
    st.subheader("파트 C. 원칙과 실제")
    st.markdown(PART_C_INTRO)
    st.markdown("---")

    all_ids = []

    for sw_set in SW_SETS:
        st.markdown(f"#### {sw_set['title']}")
        st.markdown(
            f'<div class="scenario-text">{sw_set["scenario"]}</div>',
            unsafe_allow_html=True,
        )

        # 당위
        ought = sw_set["ought"]
        all_ids.append(ought["id"])
        st.markdown("**〈당위〉**")
        opts_o = get_options(ought["options"])
        render_radio(ought["id"], ought["text"], opts_o)

        st.markdown("")

        # 실제
        actual = sw_set["actual"]
        all_ids.append(actual["id"])
        st.markdown("**〈실제〉**")
        opts_a = get_options(actual["options"])
        render_radio(actual["id"], actual["text"], opts_a)

        st.markdown("---")

    all_answered = all(
        st.session_state.responses.get(iid) is not None
        for iid in all_ids
    )
    if all_answered:
        st.button("다음으로", on_click=next_page, type="primary")
    else:
        st.info("모든 문항에 응답해 주세요.")


def render_part_d():
    """파트 D: 사회적 쟁점 (VC)."""
    show_progress()
    st.subheader("파트 D. 사회적 쟁점")
    st.markdown(PART_D_INTRO)
    st.markdown("---")

    for item in VC_ITEMS:
        opts = get_options(item["options"])
        render_radio(item["id"], item["text"], opts)
        st.markdown("")

    all_answered = all(
        st.session_state.responses.get(item["id"]) is not None
        for item in VC_ITEMS
    )
    if all_answered:
        st.button("다음으로", on_click=next_page, type="primary")
    else:
        st.info("모든 문항에 응답해 주세요.")


def render_part_e():
    """파트 E: 마무리 및 파일럿 검증."""
    show_progress()
    st.subheader("파트 E. 마무리")
    st.markdown(PART_E_INTRO)
    st.markdown("---")

    # 피드백 문항 (E1, E2)
    for item in FEEDBACK_ITEMS:
        render_radio(item["id"], item["text"], item["options"])
        st.markdown("")

    st.markdown("---")

    # CK 문항
    for item in CK_ITEMS:
        if item["type"] == "radio":
            render_radio(item["id"], item["text"], item["options"])
        else:
            render_text(item["id"], item["text"])
        st.markdown("")

    # E1, E2 및 선택형 CK 문항 응답 확인
    required_ids = [it["id"] for it in FEEDBACK_ITEMS]
    required_ids += [it["id"] for it in CK_ITEMS if it["type"] == "radio"]

    all_answered = all(
        st.session_state.responses.get(iid) is not None
        for iid in required_ids
    )

    if all_answered:
        st.button("결과 확인하기", on_click=_compute_and_go_results, type="primary")
    else:
        st.info("선택형 문항에 모두 응답해 주세요. (서술형은 선택사항입니다.)")


def _compute_and_go_results():
    """점수 산출 후 결과 페이지로 이동."""
    _compute_scores()
    next_page()


def _compute_scores():
    """전체 점수 산출 및 세션에 저장."""
    resp = st.session_state.responses
    response_order = st.session_state.response_order

    # 1) 응답 정규화 (역방향 → 정방향 보정)
    normalized = {}

    # DQ (A1~A4) — A3은 역코딩 문항이지만 선택지 자체가 이미 역배치
    for item in DQ_ITEMS:
        raw = resp.get(item["id"])
        if raw is not None:
            n_opts = len(item["options"])
            val = normalize_response(raw, response_order, n_opts)
            # A3은 역코딩: 높은 값 = 덜 개방적으로 재코딩
            if item.get("reverse_coded"):
                val = (n_opts - 1) - val
            normalized[item["id"]] = val

    # CR (B1~B17) — FL 문항은 점수 산출에서 제외
    cr_ids = set()
    for sc in CR_SCENARIOS:
        for rel, iid in sc["item_ids"].items():
            cr_ids.add(iid)
            raw = resp.get(iid)
            if raw is not None:
                n_opts = len(sc["options"])
                normalized[iid] = normalize_response(raw, response_order, n_opts)

    # SW (C1~C6)
    for sw_set in SW_SETS:
        for part_key in ["ought", "actual"]:
            part = sw_set[part_key]
            raw = resp.get(part["id"])
            if raw is not None:
                n_opts = len(part["options"])
                normalized[part["id"]] = normalize_response(raw, response_order, n_opts)

    # VC (D1~D6)
    for item in VC_ITEMS:
        raw = resp.get(item["id"])
        if raw is not None:
            n_opts = len(item["options"])
            normalized[item["id"]] = normalize_response(raw, response_order, n_opts)

    # 2) 점수 산출
    cr_dev = compute_cr_deviations(normalized)
    sw_gaps = compute_sw_gaps(normalized)
    vc_total = compute_vc_total(normalized)
    dq_anchor = compute_dq_anchor(normalized)
    profile = determine_profile(cr_dev, sw_gaps, vc_total)

    # 3) 세션에 저장
    st.session_state.scores = {
        "cr_deviations": cr_dev,
        "sw_gaps": sw_gaps,
        "vc_total": vc_total,
        "dq_anchor": dq_anchor,
        "profile": profile,
        "normalized": normalized,
    }


def render_results():
    """결과 화면 + 성찰 질문."""
    scores = st.session_state.scores
    cr_dev = scores["cr_deviations"]
    sw_gaps = scores["sw_gaps"]
    profile = scores["profile"]

    st.header("📊 나의 종교 다양성 태도 프로파일")
    st.markdown("---")

    # ── 안내 ──
    st.markdown(
        "이 설문은 같은 상황을 종교만 바꿔 가며 제시했습니다. "
        "아래 결과는 **종교에 따라 내 반응이 얼마나 달라졌는지**를 보여줍니다."
    )
    st.markdown("")

    # ── 프로파일 유형 ──
    st.subheader(f"🏷️ 나의 유형: {profile}")
    st.markdown(PROFILE_DESCRIPTIONS.get(profile, ""))
    st.markdown("")

    # ── CR 편차 시각화 ──
    st.subheader("📏 종교별 반응 차이")
    st.markdown(
        "같은 상황인데 종교만 달랐을 때, 내 응답이 얼마나 달랐는지를 보여줍니다. "
        "**수치가 높을수록 두 종교에 대해 다르게 반응**했다는 뜻입니다."
    )

    chart_rows = []
    for pair_key, label in PAIR_LABELS.items():
        if pair_key in cr_dev:
            d = cr_dev[pair_key]
            total = d["total"]
            max_val = d["max"]
            level = get_deviation_level(total, max_val)
            ratio = (total / max_val * 100) if max_val > 0 else 0
            chart_rows.append({
                "비교 쌍": label,
                "반응 차이 (%)": round(ratio, 1),
                "수준": level,
            })

    if chart_rows:
        df = pd.DataFrame(chart_rows)
        st.bar_chart(df, x="비교 쌍", y="반응 차이 (%)", horizontal=True)

        # 해석 텍스트
        for row in chart_rows:
            level = row["수준"]
            pct = row["반응 차이 (%)"]
            pair = row["비교 쌍"]

            if pct == 0:
                emoji = "🟢"
                interpret = "두 종교에 대해 거의 같은 반응을 보였습니다."
            elif pct <= 33:
                emoji = "🟢"
                interpret = "두 종교에 대한 반응이 비슷한 편입니다."
            elif pct <= 66:
                emoji = "🟡"
                interpret = "두 종교에 대한 반응에 어느 정도 차이가 있습니다."
            else:
                emoji = "🔴"
                interpret = "두 종교에 대한 반응이 상당히 다릅니다."

            st.markdown(f"{emoji} **{pair}** — {interpret} ({pct}%)")

    st.markdown("")

    # ── SW 괴리 ──
    st.subheader("🔄 원칙과 실제 반응의 차이")
    st.markdown(
        "파트 C에서 \"이렇게 해야 한다\"고 답한 원칙과, "
        "\"실제로는 이렇게 할 것 같다\"고 답한 반응 사이에 차이가 있는지 보여줍니다."
    )

    sw_labels = ["종교적 배려 요청", "종교 간 결혼", "종교 시설 건축"]
    for label, (k, v) in zip(sw_labels, sw_gaps.items()):
        if v == 0:
            st.markdown(f"🟢 **{label}:** 원칙과 실제 반응이 일치합니다.")
        elif v > 0:
            st.markdown(
                f"🟡 **{label}:** 원칙보다 실제 반응이 좀 더 조심스러운 편입니다. "
                f"(차이: {v}단계)"
            )
        else:
            st.markdown(
                f"🔵 **{label}:** 원칙보다 실제 반응이 오히려 더 열린 편입니다. "
                f"(차이: {abs(v)}단계)"
            )

    st.markdown("")

    # ── 안내 메시지 ──
    st.info(
        "💡 **이 결과는 '진단'이 아닌 '성찰의 출발점'입니다.** "
        "누구나 종교에 따라 다르게 반응하는 부분이 있을 수 있습니다. "
        "이를 알아차리는 것 자체가 자기 이해의 첫걸음입니다."
    )

    st.markdown("---")

    # ── 성찰 질문 ──
    st.subheader("🔍 성찰 질문")
    st.markdown("아래 질문에 대한 응답은 선택사항입니다. 결과를 돌아보는 데 활용해 주세요.")

    for item in RQ_ITEMS:
        if item["type"] == "radio":
            prev = st.session_state.rq_responses.get(item["id"])
            idx = prev if prev is not None else None
            sel = st.radio(
                item["text"],
                options=item["options"],
                index=idx,
                key=f"rq_{item['id']}",
            )
            if sel is not None:
                st.session_state.rq_responses[item["id"]] = item["options"].index(sel)
        else:
            prev = st.session_state.rq_responses.get(item["id"], "")
            val = st.text_area(
                item["text"],
                value=prev if isinstance(prev, str) else "",
                key=f"rq_{item['id']}",
            )
            st.session_state.rq_responses[item["id"]] = val
        st.markdown("")

    st.markdown("---")

    # ── 데이터 저장 ──
    st.button("응답 제출 완료", on_click=_submit_data, type="primary")


def render_submitted():
    """제출 완료 화면."""
    st.markdown("")
    st.markdown("")
    st.success("✅ 응답이 성공적으로 제출되었습니다. 감사합니다!")
    st.markdown("이 페이지를 닫으셔도 됩니다.")


def _submit_data():
    """데이터 기록 실행 후 완료 페이지로 이동."""
    scores = st.session_state.scores
    flat_scores = {
        "cr_PT_IS": scores["cr_deviations"].get("PT_IS", {}).get("total", ""),
        "cr_PT_BD": scores["cr_deviations"].get("PT_BD", {}).get("total", ""),
        "cr_BD_IS": scores["cr_deviations"].get("BD_IS", {}).get("total", ""),
        "cr_T1_NR": round(scores["cr_deviations"].get("T1_NR", {}).get("total", 0), 2),
        "sw_gap_1": scores["sw_gaps"].get("set1", ""),
        "sw_gap_2": scores["sw_gaps"].get("set2", ""),
        "sw_gap_3": scores["sw_gaps"].get("set3", ""),
        "vc_total": scores["vc_total"],
        "dq_anchor": scores["dq_anchor"],
        "profile": scores["profile"],
    }

    success = log_response(
        responses=st.session_state.responses,
        scores=flat_scores,
        version=st.session_state.version,
        session_id=st.session_state.session_id,
        start_time=st.session_state.start_time,
        rq_responses=st.session_state.rq_responses,
    )
    st.session_state.data_logged = True
    next_page()


# ══════════════════════════════════════════════
# 메인 라우터
# ══════════════════════════════════════════════
def main():
    page_name = PAGES[st.session_state.page]

    # 페이지 전환 시 맨 위로 스크롤
    components.html(
        """
        <script>
            var main = window.parent.document.querySelector('section.main');
            if (main) main.scrollTo({top: 0, behavior: 'instant'});
        </script>
        """,
        height=0,
    )

    if page_name == "consent":
        render_consent()
    elif page_name == "demographics":
        render_demographics()
    elif page_name == "part_a":
        render_part_a()
    elif page_name == "part_b":
        render_part_b()
    elif page_name == "part_c":
        render_part_c()
    elif page_name == "part_d":
        render_part_d()
    elif page_name == "part_e":
        render_part_e()
    elif page_name == "results":
        render_results()
    elif page_name == "submitted":
        render_submitted()


if __name__ == "__main__":
    main()
