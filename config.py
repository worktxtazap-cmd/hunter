# Источники: юзернеймы чатов и каналов без @
SOURCES = [
    "onlayn_rabota",
    "frilancru",
    "jobospherechat",
    "profiwork",
    "proffreelancee_chat",
    "workk_onchat",
    "frilanc",
    "freelance_birzha",
    "birjafreelance",
    "freelance_in_telegram",
    "freelance_chatik0",
    "digitaltender",
    "workzavr",
    "ipomogator",

    "freelancetaverna",
]

# Что считаем заявкой
DEMAND_KEYWORDS = [
    "ищу парсер", "нужен парсер", "нужен скраппер", "спарсить",
    "нужна база", "ищу базу", "куплю базу", "база контактов",
    "нужна рассылка", "нужен инвайт", "нужен бот", "сделать бота",
    "нужен лендинг", "нужен сайт", "нужен дизайнер",
    "ищу исполнителя", "кто сделает",
]

# Если это продавец, а не покупатель
STOP_KEYWORDS = [
    "продаю",
    "предлагаю услуги",
    "подписывайтесь",
]

# Как часто опрашивать источники, секунды
POLL_INTERVAL = 60

# Сколько последних сообщений смотреть в каждом источнике
MESSAGES_PER_CHAT = 10
