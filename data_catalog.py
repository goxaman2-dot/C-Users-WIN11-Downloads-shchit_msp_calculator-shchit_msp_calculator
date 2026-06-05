
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Layer = Literal["technical", "org_legal", "economic_management", "socio_legal"]
CostType = Literal["preventive", "detection", "recovery", "legal_compliance", "socio_legal_compliance"]

@dataclass(frozen=True)
class Asset:
    id: str
    name: str
    category: str
    default_criticality: float

@dataclass(frozen=True)
class Threat:
    id: str
    name: str
    asset_ids: list[str]
    layer: Layer
    base_likelihood: float
    default_loss_share: float
    heavy_tail: float
    description: str

@dataclass(frozen=True)
class Control:
    id: str
    name: str
    layer: Layer
    cost_type: CostType
    annual_cost: int
    affected_threats: list[str]
    probability_reduction: float
    loss_reduction: float
    downtime_reduction: float

ASSETS = [
    Asset("email", "Корпоративная почта и мессенджеры", "communications", 0.82),
    Asset("website", "Сайт, формы заявок, интернет-магазин", "sales", 0.78),
    Asset("pos", "Онлайн-касса, терминалы, эквайринг", "payments", 0.86),
    Asset("crm", "CRM и клиентская база", "data", 0.88),
    Asset("personal_data", "Персональные данные клиентов и сотрудников", "regulated_data", 0.90),
    Asset("cloud", "Облачные сервисы, файлы, SaaS", "infrastructure", 0.76),
    Asset("bank", "Банк-клиент и платёжные кабинеты", "finance", 0.95),
    Asset("employees", "Сотрудники, подрядчики, внутренние доступы", "people", 0.80),
    Asset("reputation", "Доверие клиентов, жалобы, публичный след инцидента", "socio_legal", 0.92),
]

THREATS = [
    Threat("phishing_email", "Фишинг и захват корпоративной почты", ["email", "bank", "crm"], "technical", 0.52, 0.22, 1.45, "Компрометация почты, платёжных инструкций и кабинетов."),
    Threat("ransomware", "Шифровальщик и блокировка рабочих данных", ["cloud", "crm", "personal_data"], "technical", 0.22, 0.28, 1.85, "Остановка процессов, восстановление данных, простой."),
    Threat("website_outage", "Падение сайта или интернет-магазина", ["website"], "technical", 0.38, 0.18, 1.25, "Потеря заявок, рекламного трафика и доверия."),
    Threat("pos_outage", "Остановка кассы, терминалов или эквайринга", ["pos"], "economic_management", 0.34, 0.20, 1.15, "Прямой простой продаж."),
    Threat("insider_leak", "Инсайдерская выгрузка клиентской базы", ["crm", "personal_data", "employees"], "org_legal", 0.20, 0.31, 1.95, "Скрытый конкурентный ущерб."),
    Threat("pdn_leak", "Утечка персональных данных", ["personal_data", "crm", "cloud"], "socio_legal", 0.18, 0.36, 2.10, "Штрафной, социальный, репутационный и восстановительный ущерб."),
    Threat("account_takeover", "Захват облачных, рекламных или платёжных кабинетов", ["cloud", "website", "bank", "email"], "technical", 0.30, 0.24, 1.55, "Потеря контроля над каналами продаж и платежами."),
    Threat("legal_gap_pdn", "Правовой разрыв в обработке персональных данных", ["personal_data", "website", "employees"], "socio_legal", 0.46, 0.26, 1.60, "Отсутствие документов, уведомлений, оснований обработки, договоров и процедур."),
    Threat("supplier_failure", "Отказ ИТ-поставщика, хостинга или облачного сервиса", ["cloud", "website", "pos", "crm"], "economic_management", 0.28, 0.19, 1.35, "Зависимость от внешнего сервиса без резервного сценария."),
    Threat("complaints_publicity", "Жалобы субъектов ПДн и публичность инцидента", ["personal_data", "reputation", "website"], "socio_legal", 0.24, 0.22, 1.70, "Социально-правовое усиление ущерба: жалобы, публичный след, запросы, потеря доверия."),
]

CONTROLS = [
    Control("mfa", "MFA для почты, облаков, банка и администраторов", "technical", "preventive", 18000, ["phishing_email", "account_takeover"], 0.42, 0.12, 0.00),
    Control("backup_tested", "Резервное копирование с проверкой восстановления", "technical", "recovery", 42000, ["ransomware", "supplier_failure"], 0.10, 0.48, 0.38),
    Control("email_hardening", "Настройка домена почты, антифишинг, SPF/DKIM/DMARC", "technical", "preventive", 26000, ["phishing_email", "account_takeover"], 0.28, 0.10, 0.00),
    Control("access_control", "Разграничение доступов к CRM, файлам и клиентской базе", "org_legal", "preventive", 36000, ["insider_leak", "pdn_leak", "account_takeover"], 0.26, 0.30, 0.00),
    Control("offboarding", "Порядок увольнения: отзыв доступов, акты, контроль выгрузок", "org_legal", "preventive", 22000, ["insider_leak", "pdn_leak"], 0.22, 0.24, 0.00),
    Control("pdn_compliance", "Правовой комплект ПДн: политика, основания, уведомления, договоры", "socio_legal", "socio_legal_compliance", 65000, ["legal_gap_pdn", "pdn_leak", "complaints_publicity"], 0.35, 0.42, 0.00),
    Control("incident_procedure", "Процедура реагирования на инциденты и утечки", "socio_legal", "detection", 32000, ["pdn_leak", "legal_gap_pdn", "ransomware", "complaints_publicity"], 0.14, 0.32, 0.20),
    Control("employee_training", "Практическое обучение сотрудников фишингу и работе с данными", "org_legal", "preventive", 24000, ["phishing_email", "insider_leak", "pdn_leak", "complaints_publicity"], 0.24, 0.15, 0.00),
    Control("web_monitoring", "Мониторинг сайта, обновлений CMS и форм заявок", "technical", "detection", 30000, ["website_outage", "account_takeover", "pdn_leak"], 0.18, 0.16, 0.22),
    Control("reserve_internet_pos", "Резервный интернет и сценарий продаж при отказе терминала", "economic_management", "recovery", 28000, ["pos_outage", "supplier_failure"], 0.12, 0.20, 0.45),
    Control("supplier_contracts", "Договорные SLA и резервные поставщики критичных сервисов", "economic_management", "preventive", 45000, ["supplier_failure", "website_outage", "pos_outage"], 0.20, 0.24, 0.28),
    Control("crisis_fund", "Резерв затрат на восстановление после ИБ-инцидента", "economic_management", "recovery", 80000, ["ransomware", "pdn_leak", "website_outage", "supplier_failure", "complaints_publicity"], 0.00, 0.34, 0.18),
    Control("complaint_response", "Порядок ответа на запросы и жалобы субъектов ПДн", "socio_legal", "socio_legal_compliance", 27000, ["complaints_publicity", "legal_gap_pdn", "pdn_leak"], 0.22, 0.28, 0.00),
]

QUALITY_LEVELS = {
    "none": ("Мера отсутствует", 0.00),
    "paid": ("Оплачена, но не внедрена", 0.15),
    "formal": ("Внедрена формально", 0.35),
    "working": ("Работает и проверяется", 0.65),
    "embedded": ("Встроена в процесс", 0.90),
}

SECTOR_PROFILES = {
    "Розничная торговля": {"email": .70, "website": .45, "pos": 1.00, "crm": .65, "personal_data": .70, "cloud": .55, "bank": .85, "employees": .70, "reputation": .75},
    "Интернет-магазин": {"email": .85, "website": 1.00, "pos": .70, "crm": .90, "personal_data": .90, "cloud": .85, "bank": .80, "employees": .75, "reputation": .95},
    "Услуги": {"email": .80, "website": .65, "pos": .75, "crm": .75, "personal_data": .80, "cloud": .65, "bank": .70, "employees": .75, "reputation": .85},
    "B2B-компания": {"email": .95, "website": .55, "pos": .25, "crm": .90, "personal_data": .65, "cloud": .80, "bank": .85, "employees": .85, "reputation": .70},
    "Производство": {"email": .75, "website": .45, "pos": .20, "crm": .60, "personal_data": .55, "cloud": .55, "bank": .75, "employees": .80, "reputation": .55},
    "Медицина / образование": {"email": .85, "website": .70, "pos": .50, "crm": .75, "personal_data": 1.00, "cloud": .80, "bank": .65, "employees": .85, "reputation": .95},
}
