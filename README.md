# RDAP 심화버전 (adtv1) — Streamlit 설문 앱

**종교와 사회 — 나의 시선 돌아보기** 심화버전 파일럿 테스트용 설문 앱

## 개요

RDAP(Religious Diversity Attitude Profile) 심화버전 파일럿 설문을 Streamlit으로 구현한 앱입니다.

- **문항 수:** 35문항 + 파일럿 검증 8문항 + 성찰 6문항
- **소요 시간:** 약 15분 (피드백·성찰 포함 시 20~25분)
- **역균형화:** 종교 제시 순서(α/β) × 응답 선택지 순서(정방향/역방향) = 4개 조건

## 프로젝트 구조

```
rdap-adt/
├── app.py                # 메인 Streamlit 앱 (페이지 라우팅, UI 렌더링)
├── config.py             # 문항 데이터, 설정 상수
├── scoring.py            # 점수 산출 로직 (CR 편차, SW 괴리, VC 총점, 프로파일)
├── sheets_logger.py      # Google Sheets 데이터 기록 모듈
├── requirements.txt      # Python 의존성
├── .streamlit/
│   └── config.toml       # Streamlit UI 테마 설정
├── .gitignore
└── README.md
```

## 점수 산출 방식

| 지표 | 산출 방법 | 범위 |
|---|---|---|
| CR 편차 (PT-IS) | \|B1-B3\| + \|B6-B8\| + \|B11-B13\| + \|B15-B17\| | 0~12 |
| CR 편차 (PT-BD) | \|B1-B2\| + \|B6-B7\| + \|B11-B12\| + \|B15-B16\| | 0~12 |
| CR 편차 (BD-IS) | \|B2-B3\| + \|B7-B8\| + \|B12-B13\| + \|B16-B17\| | 0~12 |
| CR 편차 (T1-NR) | \|avg(B1~3)-B4\| + \|avg(B6~8)-B9\| | 0~6 |
| SW 괴리 | 실제 - 당위 (양수 = 폐쇄적) | -3~+3 per set |
| VC 방향 | D1~D6 합산 (높을수록 규범적 제한 선호) | 0~18 |

## 라이선스

본 프로젝트는 교육 및 연구 목적으로 개발되었습니다.
