"""Twenty classic four-line poems/excerpts — ten public-domain English
nursery rhymes American schoolchildren memorize, plus ten Russian ones from
19th/early-20th-century classics (Pushkin, Lermontov, Tyutchev, Fet,
Nekrasov, Surikov, Yesenin) that Russian schoolchildren memorize — used by
the Model tab's "Тест" button to generate quick queue traffic without typing
text by hand each time. Mixing both languages exercises Vocari's per-message
language auto-detection (see tts/service.py's resolve_lang) along the way."""
from __future__ import annotations

import random

EN_POEMS: list[str] = [
    "Twinkle, twinkle, little star, how I wonder what you are! "
    "Up above the world so high, like a diamond in the sky.",
    "Mary had a little lamb, its fleece was white as snow, "
    "and everywhere that Mary went, the lamb was sure to go.",
    "Row, row, row your boat, gently down the stream, "
    "merrily, merrily, merrily, merrily, life is but a dream.",
    "Rain, rain, go away, come again another day, "
    "little Johnny wants to play, rain, rain, go away.",
    "Hey diddle diddle, the cat and the fiddle, "
    "the cow jumped over the moon, the little dog laughed to see such fun.",
    "Jack and Jill went up the hill to fetch a pail of water, "
    "Jack fell down and broke his crown, and Jill came tumbling after.",
    "Baa, baa, black sheep, have you any wool? "
    "Yes sir, yes sir, three bags full.",
    "Humpty Dumpty sat on a wall, Humpty Dumpty had a great fall, "
    "all the king's horses and all the king's men couldn't put Humpty together again.",
    "Little Miss Muffet sat on a tuffet, eating her curds and whey, "
    "along came a spider who sat down beside her.",
    "One, two, buckle my shoe, three, four, knock at the door, "
    "five, six, pick up sticks, seven, eight, lay them straight.",
]

RU_POEMS: list[str] = [
    "У лукоморья дуб зелёный, златая цепь на дубе том: "
    "и днём и ночью кот учёный всё ходит по цепи кругом.",
    "Мороз и солнце — день чудесный! Ещё ты дремлешь, друг прелестный. "
    "Пора, красавица, проснись, открой сомкнуты негой взоры.",
    "Буря мглою небо кроет, вихри снежные крутя; "
    "то, как зверь, она завоет, то заплачет, как дитя.",
    "Белеет парус одинокой в тумане моря голубом. "
    "Что ищет он в стране далёкой? Что кинул он в краю родном?",
    "Выхожу один я на дорогу; сквозь туман кремнистый путь блестит; "
    "ночь тиха, пустыня внемлет богу, и звезда с звездою говорит.",
    "Белая берёза под моим окном принакрылась снегом, точно серебром. "
    "На пушистых ветках снежною каймой распустились кисти белой бахромой.",
    "Люблю грозу в начале мая, когда весенний, первый гром, "
    "как бы резвяся и играя, грохочет в небе голубом.",
    "Я пришёл к тебе с приветом рассказать, что солнце встало, "
    "что оно горячим светом по листам затрепетало.",
    "Однажды, в студёную зимнюю пору, я из лесу вышел; был сильный мороз. "
    "Гляжу, поднимается медленно в гору лошадка, везущая хворосту воз.",
    "Вот моя деревня, вот мой дом родной, "
    "вот качусь я в санках по горе крутой.",
]

POEMS: list[str] = EN_POEMS + RU_POEMS


def random_poem() -> str:
    return random.choice(POEMS)
