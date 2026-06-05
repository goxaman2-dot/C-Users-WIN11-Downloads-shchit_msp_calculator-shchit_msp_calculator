
from __future__ import annotations
import altair as alt
import pandas as pd
import streamlit as st
from data_catalog import ASSETS, CONTROLS, QUALITY_LEVELS, SECTOR_PROFILES
from legal_fines import calculate_legal_fines
from risk_engine import calculate_risk_table, calculate_summary, greedy_cost_plan, layer_summary, marginal_control_effect, protection_costs

st.set_page_config(page_title="Щит-МСП: остаточный риск и штрафы", page_icon="🛡️", layout="wide")
st.title("🛡️ Щит-МСП")
st.subheader("Калькулятор остаточного информационного риска, защитных затрат и возможных штрафов")

st.markdown("ИБ считается как защитная функция: не ROI, не инвестиции, а **затраты на снижение остаточного риска и правового несоответствия**.")

with st.sidebar:
    st.header("1. Профиль МСП")
    sector = st.selectbox("Сфера деятельности", list(SECTOR_PROFILES.keys()), index=0)
    monthly_revenue = st.number_input("Средняя месячная выручка, руб.", 100_000, 500_000_000, 3_000_000, 100_000)
    online_share = st.slider("Доля онлайн-продаж / цифровых заявок, %", 0, 100, 35)
    tolerated_downtime_hours = st.slider("Допустимый простой, часов", 1, 120, 8)
    critical_loss_threshold = st.number_input("Критический ущерб для устойчивости МСП, руб.", 50_000, 500_000_000, 1_500_000, 50_000)
    st.header("2. Люди и данные")
    staff_with_access = st.slider("Сотрудников с доступом к данным / кабинетам", 1, 250, 8)
    has_remote_work = st.checkbox("Есть удалённый доступ", value=True)
    has_contractors = st.checkbox("Есть подрядчики с доступом к данным или сервисам", value=True)
    has_pdn = st.checkbox("Обрабатываются персональные данные", value=True)
    pdn_subjects = st.number_input("Оценка числа субъектов ПДн", 0, 5_000_000, 1200, 100, disabled=not has_pdn)

st.header("3. Карта активов")
asset_options = {a.name: a.id for a in ASSETS}
default_assets = [a.name for a in ASSETS]
selected_asset_names = st.multiselect("Выберите активы, значимые для бизнеса", list(asset_options.keys()), default=default_assets)
selected_asset_ids = [asset_options[n] for n in selected_asset_names]

st.header("4. Текущие меры и качество внедрения")
quality_options = {label: key for key, (label, _) in QUALITY_LEVELS.items()}
selected_quality = {}
cols = st.columns(3)
for idx, c in enumerate(CONTROLS):
    with cols[idx % 3]:
        label = st.selectbox(c.name, list(quality_options.keys()), index=0, key=f"q_{c.id}")
        selected_quality[c.id] = quality_options[label]

risk_kwargs = dict(
    sector=sector,
    selected_asset_ids=selected_asset_ids,
    monthly_revenue=float(monthly_revenue),
    critical_loss_threshold=float(critical_loss_threshold),
    tolerated_downtime_hours=float(tolerated_downtime_hours),
    staff_with_access=int(staff_with_access),
    has_remote_work=has_remote_work,
    has_contractors=has_contractors,
    has_pdn=has_pdn,
    pdn_subjects=int(pdn_subjects),
    online_share=float(online_share),
)

risk_df = calculate_risk_table(**risk_kwargs, selected_quality=selected_quality)
summary = calculate_summary(risk_df, float(critical_loss_threshold))
layers = layer_summary(risk_df)
costs_df = protection_costs(selected_quality)

pdn_incident_base = 0.18
if not risk_df.empty and "pdn_leak" in set(risk_df["id"]):
    pdn_incident_base = float(risk_df[risk_df["id"] == "pdn_leak"]["Вероятность"].iloc[0])

fine_rows, fine_summary = calculate_legal_fines(
    has_pdn=has_pdn,
    monthly_revenue=float(monthly_revenue),
    pdn_subjects=int(pdn_subjects),
    selected_quality=selected_quality,
    has_contractors=has_contractors,
    staff_with_access=int(staff_with_access),
    online_share=float(online_share),
    base_incident_probability=pdn_incident_base,
)
fine_df = pd.DataFrame(fine_rows)

st.header("5. Итоговый результат")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Исходный риск", f"{summary['base_risk']:,.0f} руб.".replace(",", " "))
m2.metric("Остаточный риск", f"{summary['residual_risk']:,.0f} руб.".replace(",", " "))
m3.metric("Остаточный риск", f"{summary['residual_percent']:.1f}%")
m4.metric("Индекс критического ущерба", f"{summary['critical_exceedance_proxy']:.1f}%")

st.subheader("6. Возможные штрафы и правовая стоимость несоблюдения")
lm1, lm2, lm3, lm4 = st.columns(4)
lm1.metric("Правовой разрыв", f"{fine_summary['legal_gap_score']:.1f}%")
lm2.metric("Коэффициент выявления", f"{fine_summary['detection_probability']:.1f}%")
lm3.metric("Ожидаемый штрафной ущерб", f"{fine_summary['expected_legal_fines_mid']:,.0f} руб.".replace(",", " "))
lm4.metric("Диапазон ожидаемого штрафного ущерба", f"{fine_summary['expected_legal_fines_min']:,.0f}–{fine_summary['expected_legal_fines_max']:,.0f} руб.".replace(",", " "))
st.caption("Штрафы показаны как экономическая стоимость правового несоответствия. Это не юридическое заключение и не прогноз решения суда.")

with st.expander("Таблица возможных штрафных сценариев", expanded=True):
    if not has_pdn:
        st.info("Правовой блок штрафов не активирован: персональные данные не отмечены.")
    else:
        st.dataframe(fine_df[["Сценарий штрафа", "Норма", "Вероятностный коэффициент", "Штраф минимум, руб.", "Штраф максимум, руб.", "Ожидаемый штраф средний, руб.", "Условие"]], use_container_width=True)

if not layers.empty:
    st.subheader("7. Остаточный риск по трём слоям")
    st.altair_chart(alt.Chart(layers).mark_bar().encode(x="Остаточный риск, %:Q", y=alt.Y("Слой:N", sort="-x"), tooltip=list(layers.columns)).properties(height=180), use_container_width=True)

st.subheader("8. Факторы остаточного риска")
if risk_df.empty:
    st.warning("Выберите хотя бы один актив.")
else:
    top = risk_df.sort_values("Остаточный риск, руб.", ascending=False).head(10)
    st.altair_chart(alt.Chart(top).mark_bar().encode(x="Остаточный риск, руб.:Q", y=alt.Y("Угроза / правовой разрыв:N", sort="-x"), tooltip=["Угроза / правовой разрыв", "Слой", "Исходный риск, руб.", "Остаточный риск, руб.", "Применённые меры"]).properties(height=360), use_container_width=True)
    st.dataframe(risk_df[["Угроза / правовой разрыв", "Слой", "Вероятность", "Уязвимость", "Оценка ущерба, руб.", "Исходный риск, руб.", "Остаточный риск, руб.", "Остаточный риск, %", "Применённые меры"]].sort_values("Остаточный риск, руб.", ascending=False), use_container_width=True)

st.header("9. Защитные затраты и очередь усиления")
st.metric("Учтённые годовые защитные затраты", f"{int(costs_df['Учтённые годовые затраты, руб.'].sum()):,.0f} руб.".replace(",", " "))
with st.expander("Структура защитных затрат"):
    st.dataframe(costs_df, use_container_width=True)

max_budget = st.number_input("Предел дополнительных защитных затрат, руб.", 0, 50_000_000, 150_000, 10_000)
effect_df = marginal_control_effect(current_quality=selected_quality, **risk_kwargs)
plan_df = greedy_cost_plan(effect_df, int(max_budget))
left, right = st.columns(2)
with left:
    st.subheader("Очередность мер")
    st.dataframe(effect_df.head(12), use_container_width=True)
with right:
    st.subheader("Портфель в пределах заданных затрат")
    if plan_df.empty:
        st.info("В заданный предел затрат не вошла ни одна дополнительная мера.")
    else:
        st.dataframe(plan_df, use_container_width=True)
        st.metric("Сумма дополнительных затрат", f"{int(plan_df['Дополнительные защитные затраты, руб.'].sum()):,.0f} руб.".replace(",", " "))
        st.metric("Расчётное снижение остаточного риска", f"{float(plan_df['Снижение остаточного риска, руб.'].sum()):,.0f} руб.".replace(",", " "))

st.header("10. Ограничения")
st.markdown("""
1. Калькулятор не заменяет технический аудит и юридическое заключение.
2. Итоговый процент — нормированный индекс остаточного риска, а не абсолютная вероятность взлома.
3. Штрафные сценарии требуют актуализации по действующей редакции закона и практике.
4. Защитные меры учитываются через качество внедрения, а не через факт оплаты.
""")
