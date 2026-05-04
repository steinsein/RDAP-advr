"""
RDAP 심화버전 (adtv1) — Google Sheets 데이터 기록 모듈
"""

import json
from datetime import datetime

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def get_gspread_client():
    """서비스 계정 인증 및 gspread 클라이언트 반환."""
    try:
        creds_info = st.secrets["gcp_service_account"]
        # secrets.toml에서 dict 또는 JSON 문자열로 제공될 수 있음
        if isinstance(creds_info, str):
            creds_dict = json.loads(creds_info)
        else:
            creds_dict = dict(creds_info)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Google Sheets 인증 실패: {e}")
        return None


def log_response(
    responses: dict,
    scores: dict,
    version: str,
    session_id: str,
    start_time: datetime,
    rq_responses: dict | None = None,
):
    """응답 데이터를 Google Sheets에 기록.

    Args:
        responses: 전체 설문 응답 {item_id: raw_value}
        scores: 산출 점수 dict
        version: 역균형화 버전 (예: "A_forward")
        session_id: 세션 고유 ID
        start_time: 설문 시작 시각
        rq_responses: 성찰 질문 응답 (선택사항)
    """
    client = get_gspread_client()
    if client is None:
        st.warning("Google Sheets 연결이 설정되지 않았습니다. 응답이 로컬에만 저장됩니다.")
        return False

    try:
        sheet_id = st.secrets["sheets"]["spreadsheet_id"]
        sheet = client.open_by_key(sheet_id)
    except Exception as e:
        st.warning(f"스프레드시트 접근 실패: {e}")
        return False

    now = datetime.now()
    completion_seconds = int((now - start_time).total_seconds())

    # ── raw_responses 시트 ──
    try:
        raw_ws = sheet.worksheet("raw_responses")
    except gspread.WorksheetNotFound:
        raw_ws = sheet.add_worksheet(title="raw_responses", rows=1000, cols=80)
        # 헤더 행 작성
        headers = _build_raw_headers()
        raw_ws.append_row(headers)

    row = [
        now.isoformat(),
        session_id,
        version,
    ]

    # 설문 응답을 정렬된 순서로 추가
    item_order = _get_item_order()
    for item_id in item_order:
        row.append(str(responses.get(item_id, "")))

    # 성찰 질문 응답
    rq_ids = ["RQ-01", "RQ-02", "RQ-03", "RQ-04", "RQ-05", "RQ-06"]
    if rq_responses:
        for rq_id in rq_ids:
            row.append(str(rq_responses.get(rq_id, "")))
    else:
        row.extend([""] * len(rq_ids))

    row.append(str(completion_seconds))
    row.append("True")

    try:
        raw_ws.append_row(row, value_input_option="RAW")
    except Exception as e:
        st.warning(f"raw_responses 기록 실패: {e}")
        return False

    # ── computed_scores 시트 ──
    try:
        scores_ws = sheet.worksheet("computed_scores")
    except gspread.WorksheetNotFound:
        scores_ws = sheet.add_worksheet(title="computed_scores", rows=1000, cols=20)
        score_headers = [
            "session_id", "version",
            "cr_PT_IS", "cr_PT_BD", "cr_BD_IS", "cr_T1_NR",
            "sw_gap_1", "sw_gap_2", "sw_gap_3",
            "vc_total", "dq_anchor", "profile",
        ]
        scores_ws.append_row(score_headers)

    score_row = [
        session_id,
        version,
        scores.get("cr_PT_IS", ""),
        scores.get("cr_PT_BD", ""),
        scores.get("cr_BD_IS", ""),
        scores.get("cr_T1_NR", ""),
        scores.get("sw_gap_1", ""),
        scores.get("sw_gap_2", ""),
        scores.get("sw_gap_3", ""),
        scores.get("vc_total", ""),
        scores.get("dq_anchor", ""),
        scores.get("profile", ""),
    ]

    try:
        scores_ws.append_row(score_row, value_input_option="RAW")
    except Exception as e:
        st.warning(f"computed_scores 기록 실패: {e}")
        return False

    return True


def _get_item_order() -> list:
    """기록 순서대로 정렬된 문항 ID 목록."""
    order = []
    # SC
    order.extend(["SC-01", "SC-02"])
    # DM
    order.extend(["DM-01", "DM-02", "DM-04", "DM-05", "DM-06", "DM-07", "DM-08", "DM-09"])
    # DQ (Part A)
    order.extend(["A1", "A2", "A3", "A4"])
    # CR + FL (Part B) — 문항 번호 순
    order.extend([
        "B1", "B2", "B3", "B4",        # S1
        "B5",                            # FL-01
        "B6", "B7", "B8", "B9",        # S2
        "B10",                           # FL-02
        "B11", "B12", "B13",            # S3
        "B14",                           # FL-03
        "B15", "B16", "B17",            # S4
    ])
    # SW (Part C)
    order.extend(["C1", "C2", "C3", "C4", "C5", "C6"])
    # VC (Part D)
    order.extend(["D1", "D2", "D3", "D4", "D5", "D6"])
    # Feedback + CK (Part E)
    order.extend(["E1", "E2", "CK-01", "CK-02", "CK-03", "CK-04", "CK-05", "CK-06"])
    return order


def _build_raw_headers() -> list:
    """raw_responses 시트 헤더 행."""
    headers = ["timestamp", "session_id", "version"]
    headers.extend(_get_item_order())
    headers.extend(["RQ-01", "RQ-02", "RQ-03", "RQ-04", "RQ-05", "RQ-06"])
    headers.extend(["completion_seconds", "completed"])
    return headers
