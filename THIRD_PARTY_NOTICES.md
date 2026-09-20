# Сторонние компоненты и материалы

WordByHeart распространяется на условиях GNU General Public License v3.0 only
(`GPL-3.0-only`). Приложение использует перечисленные ниже сторонние
компоненты. Каждый компонент сохраняет собственную лицензию и права его
авторов.

Большинство библиотек, программ, моделей и словарных данных не входят в
репозиторий WordByHeart: установщик загружает их с официальных источников на
компьютер пользователя.

## Шрифт

| Компонент | Назначение и лицензия | Официальная ссылка |
|---|---|---|
| Roboto Condensed Regular и SemiBold | Шрифт интерфейса. SIL Open Font License 1.1 (`OFL-1.1`). Полный текст лицензии находится в `src/fonts/Roboto_Condensed/OFL.txt`. | [Roboto](https://github.com/googlefonts/roboto-classic), [OFL 1.1](https://openfontlicense.org/open-font-license-official-text/) |

## Python и установка

| Компонент | Назначение и лицензия | Официальная ссылка |
|---|---|---|
| CPython | Среда выполнения приложения. Python Software Foundation License Version 2. Если подходящий Python не установлен, WordByHeart загружает официальный CPython с python.org. | [Лицензия Python](https://docs.python.org/3/license.html), [python.org](https://www.python.org/downloads/) |
| Tcl/Tk и Tkinter | Основа графического интерфейса. Tcl/Tk License. Поставляется вместе с официальным Python. | [Лицензия Tcl/Tk](https://www.tcl-lang.org/software/tcltk/license.html) |
| pip | Установка Python-пакетов. MIT License. | [pip LICENSE](https://github.com/pypa/pip/blob/main/LICENSE.txt) |
| setuptools | Сборка и установка Python-пакета WordByHeart. MIT License. | [setuptools LICENSE](https://github.com/pypa/setuptools/blob/main/LICENSE) |

## Python-библиотеки

| Библиотека | Назначение и лицензия | Официальная ссылка |
|---|---|---|
| CustomTkinter | Графический интерфейс. MIT License. | [CustomTkinter LICENSE](https://github.com/TomSchimansky/CustomTkinter/blob/master/LICENSE) |
| spaCy | Анализ текста, лемматизация и грамматические признаки. MIT License. Модели spaCy имеют отдельные лицензии, указанные ниже. | [spaCy LICENSE](https://github.com/explosion/spaCy/blob/master/LICENSE) |
| pandas | Работа с табличными данными. BSD 3-Clause License. | [pandas LICENSE](https://github.com/pandas-dev/pandas/blob/main/LICENSE) |
| PyArrow | Хранение промежуточных данных в формате Parquet. Apache License 2.0. | [Arrow LICENSE](https://github.com/apache/arrow/blob/main/LICENSE.txt), [Arrow NOTICE](https://github.com/apache/arrow/blob/main/NOTICE.txt) |
| openpyxl | Чтение и создание XLSX-файлов. MIT License. | [openpyxl LICENCE](https://foss.heptapod.net/openpyxl/openpyxl/-/blob/branch/3.1/LICENCE.rst) |
| python-docx | Чтение шаблона и создание карточек DOCX. MIT License. | [python-docx LICENSE](https://github.com/python-openxml/python-docx/blob/master/LICENSE) |
| phonemizer | Связь приложения с eSpeak NG для создания транскрипций. GNU GPL v3.0 or later. | [phonemizer LICENSE](https://github.com/bootphon/phonemizer/blob/master/LICENSE) |
| wordfreq | Оценка общеязыковой частотности слов. Код — Apache License 2.0; данные — преимущественно CC BY-SA 4.0 и материалы с отдельными требованиями атрибуции. | [Лицензия и источники wordfreq](https://github.com/rspeer/wordfreq#license) |
| OpenAI Python SDK | Подключение к OpenAI API при включённом переводе через модель. Apache License 2.0. | [openai-python LICENSE](https://github.com/openai/openai-python/blob/main/LICENSE) |
| HTTPX | Загрузка словарных данных и сетевые запросы. BSD 3-Clause License. | [HTTPX LICENSE](https://github.com/encode/httpx/blob/master/LICENSE.md) |
| charset-normalizer | Определение кодировки текстовых файлов. MIT License. | [charset-normalizer LICENSE](https://github.com/jawah/charset_normalizer/blob/master/LICENSE) |
| python-dotenv | Загрузка локальных настроек и API-ключа из `.env`. BSD 3-Clause License. | [python-dotenv LICENSE](https://github.com/theskumar/python-dotenv/blob/main/LICENSE) |
| Pydantic и pydantic-core | Проверка настроек и структурированных данных. MIT License. | [Pydantic LICENSE](https://github.com/pydantic/pydantic/blob/main/LICENSE), [pydantic-core LICENSE](https://github.com/pydantic/pydantic-core/blob/main/LICENSE) |
| tqdm | Отображение прогресса обработки и загрузки. MPL 2.0 и MIT для соответствующих частей проекта. | [tqdm LICENCE](https://github.com/tqdm/tqdm/blob/master/LICENCE) |
| PyYAML | Чтение конфигурационных YAML-файлов. MIT License. | [PyYAML LICENSE](https://github.com/yaml/pyyaml/blob/main/LICENSE) |
| filelock | Защита рабочих файлов от одновременной записи. Лицензия зависит от установленной версии: актуальные версии используют MIT, более ранние версии — Unlicense. | [filelock LICENSE](https://github.com/tox-dev/filelock/blob/main/LICENSE) |

Полный список прямых Python-зависимостей и ограничения их версий указаны в
[`pyproject.toml`](pyproject.toml). Дополнительные зависимости устанавливаются
автоматически вместе с перечисленными пакетами и содержат собственные
лицензионные уведомления.

## Модели обработки языка

| Модель или компонент | Назначение и лицензия | Официальная ссылка |
|---|---|---|
| `en_core_web_trf` | Английская модель spaCy. MIT License. При её создании использовались OntoNotes 5, WordNet 3.0 и RoBERTa. | [Официальный релиз](https://github.com/explosion/spacy-models/releases/tag/en_core_web_trf-3.8.0) |
| `es_dep_news_trf` | Испанская модель spaCy. GNU GPL 3.0. При её создании использовались UD Spanish AnCora, spaCy lookups data и BETO. | [Официальный релиз](https://github.com/explosion/spacy-models/releases/tag/es_dep_news_trf-3.8.0) |
| BETO (`bert-base-spanish-wwm-cased`) | Компонент испанской модели. Авторы указывают CC BY 4.0 как лицензию, лучше всего отражающую их намерения, но предупреждают, что лицензии некоторых обучающих данных могут иметь дополнительные ограничения, особенно при коммерческом использовании. | [BETO — License Disclaimer](https://huggingface.co/dccuchile/bert-base-spanish-wwm-cased#license-disclaimer) |
| spaCy Curated Transformers | Поддержка transformer-моделей spaCy. MIT License. | [LICENSE](https://github.com/explosion/spacy-curated-transformers/blob/main/LICENSE) |
| PyTorch | Выполнение transformer-моделей. BSD 3-Clause License. | [PyTorch LICENSE](https://github.com/pytorch/pytorch/blob/main/LICENSE) |

## Программы, словарные данные и внешние сервисы

| Компонент | Назначение и лицензия | Официальная ссылка |
|---|---|---|
| eSpeak NG | Создание транскрипций IPA. GNU GPL v3.0 or later. WordByHeart загружает официальный eSpeak NG либо использует установленную пользователем копию. | [eSpeak NG COPYING](https://github.com/espeak-ng/espeak-ng/blob/1.52.0/COPYING), [релиз 1.52.0](https://github.com/espeak-ng/espeak-ng/releases/tag/1.52.0) |
| Kaikki / Wiktionary | Источник словарных переводов. Данные Kaikki извлечены из Wiktionary. Текст Wiktionary обычно распространяется по CC BY-SA 4.0 и, где применимо, GFDL; отдельные материалы могут иметь дополнительные условия. WordByHeart автоматически отбирает и преобразует данные для создаваемых словарей и карточек. | [Kaikki](https://kaikki.org/dictionary/rawdata.html), [Wiktionary: авторские права](https://en.wiktionary.org/wiki/Wiktionary:Copyrights), [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| OpenAI API и удалённые модели | Необязательный способ перевода. Пользователь предоставляет собственный API-ключ. Использование API регулируется условиями OpenAI; лицензия OpenAI Python SDK не распространяется на сервис и модели. | [Условия OpenAI](https://openai.com/policies/services-agreement/), [Правила использования](https://openai.com/policies/usage-policies/) |

WordByHeart не предоставляет гарантий в отношении сторонних компонентов и не
изменяет условия их лицензий. Актуальные условия следует проверять по
официальным ссылкам соответствующих проектов.