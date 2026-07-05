from os import getenv


CONSENT_CALLBACK = "personal_data_consent_accept"
CONSENT_DOCUMENT_VERSION = "personal-data-consent-2026-07-05"
DEFAULT_CONSENT_DOCUMENT_URL = (
    "https://github.com/makssabdal-ai/aiogram-bot/blob/master/docs/personal_data_consent.md"
)


def consent_document_url() -> str:
    return getenv("PERSONAL_DATA_CONSENT_URL") or DEFAULT_CONSENT_DOCUMENT_URL


def telegram_consent_text() -> str:
    url = consent_document_url()
    return (
        "<b>Нужно согласие на обработку персональных данных</b>\n\n"
        "Чтобы пользоваться ботом, необходимо дать отдельное согласие на обработку "
        "персональных данных для связи, оформления заказа, хранения заявки и передачи "
        "информации администратору.\n\n"
        f"Перед нажатием кнопки ознакомьтесь с документом: <a href=\"{url}\">"
        "Согласие на обработку персональных данных</a>.\n\n"
        "Нажимая кнопку ниже, Вы подтверждаете: «Я прочитал(а) согласие и даю "
        "согласие на обработку моих персональных данных для работы бота и оформления заказа»."
    )


def vk_consent_text() -> str:
    return (
        "Нужно согласие на обработку персональных данных\n\n"
        "Чтобы пользоваться ботом, необходимо дать отдельное согласие на обработку "
        "персональных данных для связи, оформления заказа, хранения заявки и передачи "
        "информации администратору.\n\n"
        f"Документ: {consent_document_url()}\n\n"
        "Нажимая кнопку ниже, Вы подтверждаете: «Я прочитал(а) согласие и даю "
        "согласие на обработку моих персональных данных для работы бота и оформления заказа»."
    )
