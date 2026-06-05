
from __future__ import annotations
import numpy as np
import pandas as pd
from data_catalog import CONTROLS, SECTOR_PROFILES, THREATS, QUALITY_LEVELS

LAYER_LABELS = {
    "technical": "Технический слой",
    "org_legal": "Организационно-правовой слой",
    "economic_management": "Экономико-управленческий слой",
    "socio_legal": "Социо-правовой слой штрафов и жалоб",
}

def clamp(v, low=0.0, high=1.0): return max(low, min(high, v))

def calculate_base_loss(monthly_revenue, critical_loss_threshold, downtime_hours, pdn_subjects, loss_share, heavy_tail, dep):
    daily = monthly_revenue / 30
    downtime = daily * max(downtime_hours, 1) / 8
    legal_social_scale = min(max(pdn_subjects / 1000, 0), 25) * 10000
    return max(10000, monthly_revenue * loss_share * dep + downtime + legal_social_scale + critical_loss_threshold * 0.05 * heavy_tail)

def threat_vulnerability(threat_id, staff_with_access, has_remote_work, has_contractors, has_pdn, online_share):
    v = .65
    if staff_with_access >= 5: v += .08
    if staff_with_access >= 15: v += .10
    if has_remote_work: v += .06
    if has_contractors: v += .07
    if has_pdn and threat_id in {"pdn_leak", "legal_gap_pdn", "insider_leak", "complaints_publicity"}: v += .12
    if online_share >= 50 and threat_id in {"website_outage", "account_takeover", "phishing_email", "complaints_publicity"}: v += .10
    return clamp(v, .25, 1.35)

def sector_asset_dependency(sector, asset_ids):
    profile = SECTOR_PROFILES.get(sector, {})
    return float(np.mean([profile.get(a, .65) for a in asset_ids])) if asset_ids else .7

def active_controls_quality(selected_quality):
    return {c.id: QUALITY_LEVELS.get(selected_quality.get(c.id, "none"), ("", 0))[1] for c in CONTROLS}

def calculate_risk_table(sector, selected_asset_ids, monthly_revenue, critical_loss_threshold, tolerated_downtime_hours, staff_with_access, has_remote_work, has_contractors, has_pdn, pdn_subjects, online_share, selected_quality):
    selected = set(selected_asset_ids)
    qmap = active_controls_quality(selected_quality)
    rows = []
    for t in THREATS:
        rel = [a for a in t.asset_ids if a in selected]
        if not rel: continue
        dep = sector_asset_dependency(sector, rel)
        vul = threat_vulnerability(t.id, staff_with_access, has_remote_work, has_contractors, has_pdn, online_share)
        likelihood = clamp(t.base_likelihood * (.75 + dep * .55), .01, .95)
        loss = calculate_base_loss(monthly_revenue, critical_loss_threshold, tolerated_downtime_hours, pdn_subjects if has_pdn else 0, t.default_loss_share, t.heavy_tail, dep)
        base = likelihood * vul * loss
        mult = 1.0
        controls = []
        costs = 0
        for c in CONTROLS:
            if t.id not in c.affected_threats: continue
            q = qmap.get(c.id, 0)
            if q <= 0: continue
            effect = 1 - ((1 - c.probability_reduction*q) * (1 - c.loss_reduction*q) * (1 - c.downtime_reduction*q*.45))
            effect = clamp(effect, 0, .92)
            mult *= 1 - effect
            controls.append(c.name)
            costs += int(c.annual_cost * q)
        res = base * mult
        rows.append({
            "id": t.id,
            "Угроза / правовой разрыв": t.name,
            "Слой": LAYER_LABELS[t.layer],
            "Вероятность": likelihood,
            "Уязвимость": vul,
            "Оценка ущерба, руб.": loss,
            "Исходный риск, руб.": base,
            "Остаточный риск, руб.": res,
            "Снижение риска, руб.": base-res,
            "Остаточный риск, %": res/base*100 if base else 0,
            "Применённые меры": "; ".join(controls) if controls else "нет",
            "Учтённые защитные затраты, руб.": costs,
            "Тяжёлый хвост": t.heavy_tail
        })
    return pd.DataFrame(rows)

def calculate_summary(df, critical_loss_threshold):
    if df.empty:
        return {"base_risk":0, "residual_risk":0, "residual_percent":0, "reduced_percent":0, "critical_exceedance_proxy":0}
    base = float(df["Исходный риск, руб."].sum())
    res = float(df["Остаточный риск, руб."].sum())
    tail = float((df["Остаточный риск, руб."] * df["Тяжёлый хвост"]).sum())
    critical = 1 - np.exp(-tail / max(critical_loss_threshold, 1))
    return {"base_risk":base, "residual_risk":res, "residual_percent":res/base*100 if base else 0, "reduced_percent":100-res/base*100 if base else 0, "critical_exceedance_proxy":clamp(float(critical),0,.95)*100}

def layer_summary(df):
    if df.empty: return pd.DataFrame()
    g = df.groupby("Слой", as_index=False)[["Исходный риск, руб.", "Остаточный риск, руб."]].sum()
    g["Остаточный риск, %"] = g["Остаточный риск, руб."] / g["Исходный риск, руб."] * 100
    return g.sort_values("Остаточный риск, %", ascending=False)

def protection_costs(selected_quality):
    rows = []
    for c in CONTROLS:
        label, q = QUALITY_LEVELS.get(selected_quality.get(c.id, "none"), ("Мера отсутствует", 0))
        rows.append({"Мера": c.name, "Слой": LAYER_LABELS[c.layer], "Тип затрат": c.cost_type, "Качество внедрения": label, "Коэффициент качества": q, "Базовые годовые затраты, руб.": c.annual_cost, "Учтённые годовые затраты, руб.": int(c.annual_cost*q)})
    return pd.DataFrame(rows)

def marginal_control_effect(current_quality, **kwargs):
    base_df = calculate_risk_table(selected_quality=current_quality, **kwargs)
    base_res = calculate_summary(base_df, kwargs["critical_loss_threshold"])["residual_risk"]
    rows = []
    for c in CONTROLS:
        current = current_quality.get(c.id, "none")
        if current in {"working", "embedded"}: continue
        candidate = dict(current_quality); candidate[c.id] = "working"
        cand_df = calculate_risk_table(selected_quality=candidate, **kwargs)
        cand_res = calculate_summary(cand_df, kwargs["critical_loss_threshold"])["residual_risk"]
        current_q = QUALITY_LEVELS.get(current, ("",0))[1]
        target_q = QUALITY_LEVELS["working"][1]
        add_cost = max(0, int(c.annual_cost*(target_q-current_q)))
        rows.append({"Мера": c.name, "Слой": LAYER_LABELS[c.layer], "Дополнительные защитные затраты, руб.": add_cost, "Снижение остаточного риска, руб.": base_res-cand_res, "Снижение риска на 1 руб. затрат": (base_res-cand_res)/add_cost if add_cost else 0})
    return pd.DataFrame(rows).sort_values("Снижение риска на 1 руб. затрат", ascending=False)

def greedy_cost_plan(effect_df, max_budget):
    selected=[]; spent=0
    for _, row in effect_df.iterrows():
        cost = int(row["Дополнительные защитные затраты, руб."])
        if cost>0 and spent+cost <= max_budget:
            selected.append(row); spent += cost
    return pd.DataFrame(selected) if selected else pd.DataFrame(columns=effect_df.columns)
