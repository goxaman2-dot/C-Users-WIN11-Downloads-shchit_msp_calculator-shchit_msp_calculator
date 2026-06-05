
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class FineScenario:
    id: str
    title: str
    article: str
    trigger: str
    min_fine: int
    max_fine: int
    probability_key: str
    is_turnover: bool = False

FINE_SCENARIOS = [
    FineScenario("pdn_no_processing_notice", "Неуведомление о намерении обрабатывать ПДн", "КоАП РФ ст. 13.11 ч. 10", "ПДн обрабатываются, но уведомление регулятору не подано или не подтверждено.", 100_000, 300_000, "formal"),
    FineScenario("pdn_no_leak_notice", "Неуведомление об утечке ПДн", "КоАП РФ ст. 13.11 ч. 11", "Утечка произошла, но процедура уведомления не определена или не исполняется.", 1_000_000, 3_000_000, "incident"),
    FineScenario("pdn_leak_small", "Утечка ПДн: 1–10 тыс. субъектов или 10–100 тыс. идентификаторов", "КоАП РФ ст. 13.11 ч. 12", "Утечка затрагивает малый или средний массив данных клиентов/сотрудников.", 3_000_000, 5_000_000, "incident"),
    FineScenario("pdn_leak_medium", "Утечка ПДн: 10–100 тыс. субъектов или 100 тыс.–1 млн идентификаторов", "КоАП РФ ст. 13.11 ч. 13", "Утечка затрагивает крупный массив данных, существенный для МСП.", 5_000_000, 10_000_000, "incident"),
    FineScenario("pdn_repeat_turnover", "Повторная утечка ПДн: оборотный штраф", "КоАП РФ ст. 13.11 ч. 14", "Повторная утечка после уже выявленного нарушения.", 20_000_000, 500_000_000, "repeat", True),
]

def _q(selected_quality: dict[str, str], control_id: str) -> float:
    levels = {"none": 0.0, "paid": 0.15, "formal": 0.35, "working": 0.65, "embedded": 0.90}
    return levels.get(selected_quality.get(control_id, "none"), 0.0)

def socio_legal_gap_score(*, has_pdn: bool, selected_quality: dict[str, str], has_contractors: bool, staff_with_access: int, online_share: float) -> float:
    if not has_pdn:
        return 0.0
    gap = 1.0
    gap -= 0.35 * _q(selected_quality, "pdn_compliance")
    gap -= 0.18 * _q(selected_quality, "incident_procedure")
    gap -= 0.13 * _q(selected_quality, "access_control")
    gap -= 0.08 * _q(selected_quality, "offboarding")
    gap -= 0.07 * _q(selected_quality, "employee_training")
    gap -= 0.14 * _q(selected_quality, "complaint_response")
    if has_contractors:
        gap += 0.08
    if staff_with_access >= 10:
        gap += 0.06
    if staff_with_access >= 30:
        gap += 0.06
    if online_share >= 50:
        gap += 0.05
    return max(0.05, min(1.0, gap))

def detection_probability(*, online_share: float, pdn_subjects: int, socio_legal_gap: float) -> float:
    p = 0.08 + 0.22 * socio_legal_gap
    if online_share >= 50:
        p += 0.05
    if pdn_subjects >= 1000:
        p += 0.05
    if pdn_subjects >= 10000:
        p += 0.08
    return max(0.02, min(0.65, p))

def incident_probability_proxy(*, base_incident_probability: float, socio_legal_gap: float) -> float:
    return max(0.01, min(0.55, base_incident_probability * (0.65 + socio_legal_gap)))

def applicability(scenario_id: str, pdn_subjects: int, has_pdn: bool) -> float:
    if not has_pdn:
        return 0.0
    if scenario_id == "pdn_leak_small" and pdn_subjects < 1000:
        return 0.35
    if scenario_id == "pdn_leak_medium" and pdn_subjects < 10_000:
        return 0.15
    if scenario_id == "pdn_repeat_turnover":
        return 0.08
    return 1.0

def turnover_fine_range(monthly_revenue: float) -> tuple[int, int]:
    annual = monthly_revenue * 12
    low = int(max(20_000_000, annual * 0.01))
    high = int(min(500_000_000, max(low, annual * 0.03)))
    return low, high

def calculate_legal_fines(*, has_pdn: bool, monthly_revenue: float, pdn_subjects: int, selected_quality: dict[str, str], has_contractors: bool, staff_with_access: int, online_share: float, base_incident_probability: float):
    gap = socio_legal_gap_score(has_pdn=has_pdn, selected_quality=selected_quality, has_contractors=has_contractors, staff_with_access=staff_with_access, online_share=online_share)
    p_detect = detection_probability(online_share=online_share, pdn_subjects=pdn_subjects, socio_legal_gap=gap)
    p_incident = incident_probability_proxy(base_incident_probability=base_incident_probability, socio_legal_gap=gap)

    rows = []
    for s in FINE_SCENARIOS:
        a = applicability(s.id, pdn_subjects, has_pdn)
        if s.probability_key == "formal":
            p = gap * p_detect * a
        elif s.probability_key == "incident":
            p = p_incident * p_detect * a
        else:
            p = p_incident * p_detect * gap * a * 0.35
        min_f, max_f = (s.min_fine, s.max_fine)
        if s.is_turnover:
            min_f, max_f = turnover_fine_range(monthly_revenue)
        rows.append({
            "Сценарий штрафа": s.title,
            "Норма": s.article,
            "Условие": s.trigger,
            "Вероятностный коэффициент": p,
            "Штраф минимум, руб.": min_f,
            "Штраф максимум, руб.": max_f,
            "Ожидаемый штраф минимум, руб.": p * min_f,
            "Ожидаемый штраф максимум, руб.": p * max_f,
            "Ожидаемый штраф средний, руб.": p * ((min_f + max_f) / 2),
        })

    return rows, {
        "socio_legal_gap_score": gap * 100,
        "detection_probability": p_detect * 100,
        "incident_probability_proxy": p_incident * 100,
        "expected_legal_fines_mid": sum(r["Ожидаемый штраф средний, руб."] for r in rows),
        "expected_legal_fines_min": sum(r["Ожидаемый штраф минимум, руб."] for r in rows),
        "expected_legal_fines_max": sum(r["Ожидаемый штраф максимум, руб."] for r in rows),
    }
