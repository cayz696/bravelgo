"""Multi-language UI labels for Play Console / Google Docs (fallback locators)."""
from __future__ import annotations

import re

# Any match in list works for get_by_role(..., name=re.compile(...))


def _pat(labels: list[str]) -> re.Pattern[str]:
    # Labels like "^Game$" are intentional regexes; plain labels stay escaped.
    esc = [l if l.startswith("^") or l.endswith("$") else re.escape(l) for l in labels]
    return re.compile("|".join(esc), re.I)


SAVE = _pat([
    "Save", "Зберегти", "Сохранить", "Speichern", "Enregistrer", "Guardar", "Opslaan", "Salva",
])
NEXT = _pat(["Next", "Далі", "Далее", "Weiter", "Suivant", "Siguiente", "Volgende", "Avanti"])
BACK = _pat(["Back", "Назад", "Zurück", "Retour"])
DASHBOARD = _pat(["Dashboard", "Панель", "Главная", "Übersicht"])
SHARE = _pat(["Share", "Надати доступ", "Поделиться", "Freigeben", "Partager"])
COPY_LINK = _pat(["Copy link", "Копіювати посилання", "Скопировать ссылку", "Link kopieren"])
CREATE_APP = _pat(["Create app", "Create application", "Створити додаток", "Создать приложение"])
BLANK_DOC = _pat(["Blank document", "Пустой документ", "Пустий документ", "Leeres Dokument"])
CHECK_AVAIL = _pat(["Check availability", "Проверить", "Перевірити"])
CREATE_APPLICATION_BTN = _pat(["Create application", "Создать приложение", "Створити додаток"])
VIEW_TASKS = _pat(["View tasks", "Переглянути завдання", "Посмотреть задачи"])
HIDE_TASKS = _pat(["Hide tasks", "Сховати"])
PRIVACY_POLICY_TASK = _pat(["Set privacy policy", "Политика конфиденциальности", "Політика конфіденційності"])
APP_ACCESS = _pat(["App access", "Доступ к приложению", "Доступ до додатка"])
ADS = _pat(["Ads", "Реклама", "Реклама"])
CONTENT_RATINGS = _pat(["Content rating", "Возрастные ограничения", "Рейтинг контенту"])
START_QUESTIONNAIRE = _pat(["Start questionnaire", "Начать", "Почати опитування"])
TARGET_AUDIENCE = _pat(["Target audience", "Целевая аудитория", "Цільова аудиторія"])
DATA_SAFETY = _pat(["Data safety", "Безопасность данных", "Безпека даних"])
GOVERNMENT = _pat(["Government apps", "Государственные", "Державні"])
FINANCIAL = _pat(["Financial features", "Финансовые", "Фінансові"])
HEALTH = _pat(["Health apps", "Health", "Здоровье", "Здоров'я"])
STORE_SETTINGS = _pat(["Store settings", "Настройки магазина", "Налаштування магазину"])
STORE_LISTING = _pat([
    "Create default store listing",
    "Set up your store listing",
    "Store listing",
    "Описание в магазине",
])
EDIT = _pat(["Edit", "Изменить", "Редагувати"])
ARCADE = _pat(["Arcade", "Аркады", "Аркада"])
GAME = _pat(["^Game$", "Игра", "Гра"])
FREE = _pat(["For free", "^Free$", "Бесплатно", "Безкоштовно"])
NO = _pat(["^No$", "Нет", "Ні"])
YES_ALL_FUNCTIONALITY = _pat([
    "All functionality in my app is available without any access restrictions",
    "без ограничений",
    "без обмежень",
])
NO_ADS = _pat(["does not contain ads", "не содержит рекламу", "не містить рекламу"])
NO_DATA_COLLECT = _pat([
    "Does your app collect or share",
    "collect or share any of the required user data",
    "собирает или передает",
])
NO_GOV = _pat(["not a government", "не является государственным", "не є державним"])
NO_FINANCIAL = _pat(["doesn't provide any financial", "не предоставляет финансовых", "не надає фінансових"])
NO_HEALTH = _pat(["does not have any health", "не имеет функций здоровья", "не має функцій здоров'я"])

AGE_16_17 = _pat(["16-17", "16–17", "16 to 17"])
AGE_18_OVER = _pat(["18 and over", "18+", "18 и старше", "18 років"])

DEFAULT_LANGUAGE_EN_US = _pat([
    "English (United States)",
    "English (US)",
    "en-US",
    "Английский (США)",
])
