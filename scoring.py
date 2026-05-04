"""
RDAP 심화버전 (adtv1) — 점수 산출 로직

CR 편차 점수, SW 괴리 점수, VC 방향 점수, 삼각측정 프로파일 판정
"""


def normalize_response(raw_index: int, response_order: str, n_options: int) -> int:
    """역방향 응답을 정방향 기준으로 정규화 (0-indexed).

    정방향(forward): 0=가장 개방적, 3=가장 폐쇄적
    역방향(reverse)이면 선택지 순서가 뒤집혀 제시되었으므로 원래 방향으로 복원.
    """
    if response_order == "reverse":
        return (n_options - 1) - raw_index
    return raw_index


def compute_cr_deviations(responses: dict) -> dict:
    """CR 시나리오별 종교 쌍 편차 점수 산출.

    adtv1 비교 쌍:
        PT-IS:  |B1-B3| + |B6-B8| + |B11-B13| + |B15-B17|  → 0~12
        PT-BD:  |B1-B2| + |B6-B7| + |B11-B12| + |B15-B16|  → 0~12
        BD-IS:  |B2-B3| + |B7-B8| + |B12-B13| + |B16-B17|  → 0~12
        T1-NR:  |avg(B1~3)-B4| + |avg(B6~8)-B9|             → 0~6

    Args:
        responses: dict 형태 {item_id: normalized_value(0-3), ...}
                   예: {"B1": 1, "B2": 0, "B3": 2, ...}

    Returns:
        dict 형태:
        {
            "PT_IS": {"total": int, "per_scenario": [int, ...], "max": int},
            "PT_BD": {...},
            "BD_IS": {...},
            "T1_NR": {"total": float, "per_scenario": [float, ...], "max": int},
        }
    """
    # 시나리오별 종교 문항 ID 매핑
    scenario_items = {
        "S1": {"PT": "B1", "BD": "B2", "IS": "B3", "NR-A": "B4"},
        "S2": {"PT": "B6", "BD": "B7", "IS": "B8", "NR-A": "B9"},
        "S3": {"PT": "B11", "BD": "B12", "IS": "B13"},
        "S4": {"PT": "B15", "BD": "B16", "IS": "B17"},
    }

    deviations = {}

    # --- 종교 쌍별 편차 (PT-IS, PT-BD, BD-IS) ---
    pairs = [("PT", "IS"), ("PT", "BD"), ("BD", "IS")]
    for r1, r2 in pairs:
        pair_key = f"{r1}_{r2}"
        per_scenario = []
        for sc_key, sc_map in scenario_items.items():
            id1 = sc_map.get(r1)
            id2 = sc_map.get(r2)
            if id1 and id2 and id1 in responses and id2 in responses:
                per_scenario.append(abs(responses[id1] - responses[id2]))
        deviations[pair_key] = {
            "total": sum(per_scenario),
            "per_scenario": per_scenario,
            "max": len(per_scenario) * 3,  # 각 시나리오 최대 편차 3
        }

    # --- T1-NR (Tier1 평균 vs 신종교) ---
    nr_scenarios = ["S1", "S2"]  # NR-A가 포함된 시나리오만
    t1_nr_per = []
    for sc_key in nr_scenarios:
        sc_map = scenario_items[sc_key]
        t1_ids = [sc_map[r] for r in ["PT", "BD", "IS"] if r in sc_map]
        nr_id = sc_map.get("NR-A")
        if nr_id and nr_id in responses:
            t1_vals = [responses[tid] for tid in t1_ids if tid in responses]
            if t1_vals:
                t1_avg = sum(t1_vals) / len(t1_vals)
                t1_nr_per.append(abs(t1_avg - responses[nr_id]))

    deviations["T1_NR"] = {
        "total": sum(t1_nr_per),
        "per_scenario": t1_nr_per,
        "max": len(nr_scenarios) * 3,
    }

    return deviations


def compute_sw_gaps(responses: dict) -> dict:
    """SW 당위-실제 괴리 점수 산출.

    양수 = 실제가 당위보다 폐쇄적
    음수 = 실제가 당위보다 개방적

    Args:
        responses: {"C1": val, "C2": val, "C3": val, ...}

    Returns:
        {"set1": gap, "set2": gap, "set3": gap}
    """
    sets = [("C1", "C2"), ("C3", "C4"), ("C5", "C6")]
    gaps = {}
    for i, (ought_id, actual_id) in enumerate(sets, 1):
        ought = responses.get(ought_id, 0)
        actual = responses.get(actual_id, 0)
        gaps[f"set{i}"] = actual - ought  # 양수 = 실제가 더 폐쇄적
    return gaps


def compute_vc_total(responses: dict) -> int:
    """VC 방향 점수 합산 (높을수록 규범적 제한 선호).

    D1~D6의 normalized 응답값(0~3) 합산 → 0~18
    """
    vc_ids = ["D1", "D2", "D3", "D4", "D5", "D6"]
    return sum(responses.get(vid, 0) for vid in vc_ids)


def compute_dq_anchor(responses: dict) -> int:
    """DQ 앵커 점수 합산.

    A1~A4의 normalized 응답값 합산 → 0~12
    A3은 역코딩 문항이므로 normalize 단계에서 이미 보정되어 있어야 함.
    """
    dq_ids = ["A1", "A2", "A3", "A4"]
    return sum(responses.get(did, 0) for did in dq_ids)


def determine_profile(cr_deviations: dict, sw_gaps: dict,
                      vc_total: int, n_vc: int = 6) -> str:
    """CR 편차, SW 괴리, VC 총점을 종합하여 프로파일 판정.

    Args:
        cr_deviations: compute_cr_deviations() 결과
        sw_gaps: compute_sw_gaps() 결과
        vc_total: VC 총점
        n_vc: VC 문항 수 (기본 6)

    Returns:
        프로파일 유형 문자열
    """
    # CR 평균 편차 (3개 쌍 기준, T1-NR 제외)
    main_pairs = ["PT_IS", "PT_BD", "BD_IS"]
    cr_totals = [cr_deviations[p]["total"] for p in main_pairs if p in cr_deviations]
    cr_maxes = [cr_deviations[p]["max"] for p in main_pairs if p in cr_deviations]
    if cr_maxes and sum(cr_maxes) > 0:
        cr_ratio = sum(cr_totals) / sum(cr_maxes)
    else:
        cr_ratio = 0

    # SW 평균 괴리
    sw_vals = list(sw_gaps.values())
    sw_mean = sum(sw_vals) / len(sw_vals) if sw_vals else 0

    # VC 중간값 기준
    vc_midpoint = n_vc * 1.5  # 4점 척도(0~3) 중간값 = 1.5 per item

    cr_high = cr_ratio > 0.15     # 편차가 최대치의 15% 이상
    sw_positive = sw_mean > 0.3   # 당위-실제 괴리 존재
    vc_open = vc_total < vc_midpoint  # 개방적 방향

    if not cr_high and not sw_positive and vc_open:
        return "일관적 개방"
    elif cr_high and sw_positive and vc_open:
        return "암묵적 차별"
    elif not cr_high and not sw_positive and not vc_open:
        return "자각적 보수"
    else:
        return "복합적 패턴"


def get_deviation_level(total: float, max_val: int) -> str:
    """편차 수준 텍스트 반환."""
    if max_val == 0:
        return "—"
    ratio = total / max_val
    if ratio < 0.1:
        return "매우 낮음"
    elif ratio < 0.25:
        return "낮음"
    elif ratio < 0.5:
        return "중간"
    elif ratio < 0.75:
        return "높음"
    else:
        return "매우 높음"
