"""Минималистичный i18n с автоопределением языка ОС (Windows / Linux / macOS) и фоллбэком в английский.

Использование: `tr("menu.file.open")`, с подстановкой: `tr("status.saved", path=p)`.
"""

from __future__ import annotations

import ctypes
import locale
import os
import sys

from translations_en import EN

RU: dict[str, str] = {
    # Menus
    "menu.file": "&Файл",
    "menu.file.new": "&Новый планшет…",
    "menu.file.open": "&Открыть проект…",
    "menu.file.save": "&Сохранить проект",
    "menu.file.save_as": "Сохранить проект &как…",
    "menu.file.recent": "Недавние проекты",
    "menu.file.import": "&Импорт",
    "menu.file.import_samples": "Концентрации образцов (CSV/TSV)…",
    "menu.file.import_instrument": "Раскладка с прибора…",
    "menu.file.export": "&Экспорт",
    "menu.file.export_xlsx": "Книга Excel (.xlsx)…",
    "menu.file.export_bench_html": "Печатный протокол на стол (.html)…",
    "menu.file.export_cfx": "Bio-Rad CFX Plate Setup (.csv)…",
    "menu.file.export_quantstudio": "ABI QuantStudio / StepOne (.csv)…",
    "menu.file.export_rotorgene": "Qiagen Rotor-Gene (.csv)…",
    "menu.file.export_abi_seq": "Секвенатор ABI 3130/3500 (.tsv)…",
    "menu.file.exit": "В&ыход",
    "menu.edit": "&Правка",
    "menu.edit.undo": "&Отменить",
    "menu.edit.redo": "&Повторить",
    "menu.edit.copy": "&Копировать лунки",
    "menu.edit.paste": "&Вставить лунки",
    "menu.edit.clear": "Очистить &выделенные лунки",
    "menu.edit.clear_all": "Очистить &весь планшет",
    "menu.edit.select_all": "Выделить в&се лунки",
    "menu.view": "&Вид",
    "menu.view.dark_theme": "&Тёмная тема",
    "menu.view.color_by_assay": "Окраска по &мишеням (Assay)",
    "menu.view.color_by_role": "Окраска по &ролям лунок",
    "menu.view.lang_ru": "Русский язык (RU)",
    "menu.view.lang_en": "English (EN)",
    "menu.tools": "&Инструменты",
    "menu.tools.smart_fill": "&Автозаполнение (Smart Fill)",
    "menu.tools.pipetting": "&Пошаговый помощник раскапки…",
    "menu.tools.load_demo": "Загрузить &демо-планшет",
    "menu.help": "&Справка",
    "menu.help.about": "О программе platekit",

    # Toolbar
    "tb.new": "Новый",
    "tb.open": "Открыть",
    "tb.save": "Сохранить",
    "tb.undo": "Отменить",
    "tb.redo": "Повторить",
    "tb.clear": "Очистить",
    "tb.pipetting": "Режим раскапки",
    "tb.export_xlsx": "Excel (.xlsx)",
    "tb.export_bench": "Протокол А4",
    "tb.format": "Формат:",
    "tb.color_mode": "Окраска:",
    "tb.color.assay": "По мишеням",
    "tb.color.role": "По типу лунок",
    "tb.lang": "Язык:",

    # Preview modes
    "preview.bench_html": "Печатный протокол на стол (HTML)",
    "preview.cfx": "Bio-Rad CFX Plate Setup (CSV)",
    "preview.quantstudio": "ABI QuantStudio / StepOne (CSV)",
    "preview.rotorgene": "Qiagen Rotor-Gene Q (CSV)",
    "preview.abi_seq": "Секвенатор ABI 3130/3500 (TSV)",
    "bench.title": "Лабораторный протокол platekit — {name}",
    "bench.meta": "Формат: <b>{fmt}</b> &nbsp;|&nbsp; Оператор: <b>{op}</b> &nbsp;|&nbsp; Протокол: <b>{proto}</b> &nbsp;|&nbsp; Создан: {dt}",
    "bench.sec1": "1. Схема планшета (занято лунок: {occ}/{tot})",
    "bench.sec2": "2. Приготовление Master Mix",
    "bench.sec3": "3. Нормализация ДНК и внесение матрицы",
    "bench.col.done": "Отм.",
    "bench.total_mix": "Общий объём Master Mix:",

    # Serial standards dialog
    "serial.title": "Серийные разведения стандартов (STD)",
    "serial.start_qty": "Стартовое кол-во копий / конц.:",
    "serial.factor": "Шаг разведения (напр. 10×):",
    "serial.steps": "Число точек (шагов):",

    # Tabs
    "tab.plate": "Конструктор планшета",
    "tab.mix": "Калькулятор Master Mix",
    "tab.norm": "Нормализация ДНК",
    "tab.export": "Протокол и экспорт в приборы",

    # Roles
    "role.unknown": "Unknown (Образец)",
    "role.ntc": "NTC (Отриц. контроль)",
    "role.pos": "POS (Полож. контроль)",
    "role.std": "STD (Стандарт)",
    "role.ipc": "IPC (Внутр. контроль)",
    "role.empty": "Пусто",

    # Inspector / Smart Fill
    "insp.plate_title": "Параметры планшета",
    "insp.plate_name": "Название:",
    "insp.operator": "Оператор:",
    "insp.selection_title": "Выбрано лунок ({n})",
    "insp.sample_name": "Образец:",
    "insp.sample_conc": "Конц. ДНК (нг/мкл):",
    "insp.assay_name": "Мишень / Assay:",
    "insp.well_role": "Тип лунки:",
    "insp.rep_group": "Группа повторов:",
    "insp.std_conc": "Конц./копии стандарта:",
    "insp.note": "Примечание:",
    "insp.apply_selected": "Применить к выделенным",
    "insp.clear_selected": "Очистить выделенные",

    "smart.title": "Быстрое заполнение (Smart Fill)",
    "smart.samples_label": "Образцы (по одному в строке или Имя;Конц):",
    "smart.samples_placeholder": "Sample_01; 45.2\nSample_02; 18.5\nSample_03; 62.0",
    "smart.assays_label": "Мишени / Праймеры (по одной в строке):",
    "smart.assays_placeholder": "ACTB\nBRCA1_ex11",
    "smart.replicates": "Повторы:",
    "smart.direction": "Направление:",
    "smart.dir.row": "По строкам (A1 → A12)",
    "smart.dir.col": "По столбцам (A1 → H1)",
    "smart.include_ntc": "Добавить NTC к каждой мишени",
    "smart.include_pos": "Добавить POS к каждой мишени",
    "smart.start_selected": "Начать с первой выделенной лунки",
    "smart.fill_btn": "Заполнить планшет",
    "smart.serial_btn": "Серийные стандарты (STD)…",
    "smart.paste_clipboard": "Вставить образцы из буфера",

    # Master Mix
    "mix.preset": "Пресет протокола:",
    "mix.rxn_vol": "Объём реакции (мкл):",
    "mix.template_vol": "Объём матрицы ДНК (мкл):",
    "mix.overfill_mode": "Режим запаса (Dead Volume):",
    "mix.overfill.percent": "Процентный (+%)",
    "mix.overfill.extra_rxn": "Доп. реакции (+N)",
    "mix.overfill.multichannel": "Многоканальный (+% и мин. +2 реакц.)",
    "mix.overfill_val": "Величина запаса:",
    "mix.recipe_title": "Состав смеси (на 1 реакцию)",
    "mix.col.component": "Компонент",
    "mix.col.stock": "Сток",
    "mix.col.final": "Конечная",
    "mix.col.vol_1x": "На 1× (мкл)",
    "mix.col.vol_total": "Всего (мкл)",
    "mix.add_comp": "+ Добавить компонент",
    "mix.remove_comp": "− Удалить выбранный",
    "mix.results_title": "Расчёт Master Mix по мишеням на планшете",
    "mix.summary_header": "Мишень: {assay} — лунок: {wells} → расчёт на {eff:.2f}× реакций (всего смеси: {total:.1f} мкл, раскапать по {disp:.1f} мкл/лунку + {tmpl:.1f} мкл ДНК)",
    "mix.no_assays": "На планшете пока нет заполненных лунок с указанной мишенью (Assay).",
    "mix.water_auto": "Вода деионизованная (milliQ, до объёма)",
    "mix.warn_exceeds": "Внимание: сумма компонентов + ДНК ({used:.2f} мкл) превышает объём реакции ({total:.2f} мкл)!",

    # DNA Normalization
    "norm.mode": "Режим расчёта:",
    "norm.mode.dilution_plate": "Нормализация до целевой концентрации (C₁V₁ = C₂V₂)",
    "norm.mode.per_reaction": "Фиксированная масса ДНК в ПЦР-реакцию (нг/реакц.)",
    "norm.target_conc": "Целевая конц. (нг/мкл):",
    "norm.final_vol": "Конечный объём разведения (мкл):",
    "norm.target_mass": "Масса ДНК в реакцию (нг):",
    "norm.max_template": "Макс. объём ДНК в ПЦР (мкл):",
    "norm.min_pipet": "Мин. точный объём дозатора (мкл):",
    "norm.import_csv": "Импорт CSV/TSV…",
    "norm.paste_btn": "Вставить таблицу (Имя / Конц)",
    "norm.sync_from_plate": "Собрать образцы с планшета",
    "norm.apply_to_plate": "Обновить концентрации на планшете",
    "norm.col.sample": "Образец",
    "norm.col.wells": "Лунки",
    "norm.col.stock": "Исходная (нг/мкл)",
    "norm.col.predilution": "Предразведение",
    "norm.col.dna_vol": "V ДНК (мкл)",
    "norm.col.diluent_vol": "V воды/буфера (мкл)",
    "norm.col.final_info": "Итог",
    "norm.col.status": "Статус QC",
    "norm.qc.ok": "OK",
    "norm.qc.too_concentrated": "Слишком конц. (V < мин, нужно 1:{factor} предразведение)",
    "norm.qc.too_dilute": "Слишком разбавлен (превышен макс. объём)",
    "norm.qc.missing_conc": "Не указана концентрация",

    # Pipetting assistant
    "pipet.title": "Пошаговый помощник раскапки (Режим у стола)",
    "pipet.mode": "Режим прохода:",
    "pipet.mode.well": "По одной лунке (1-канальный)",
    "pipet.mode.col": "По столбцам (8-канальный дозатор)",
    "pipet.mode.row": "По строкам (12-канальный дозатор)",
    "pipet.prev": "← Назад (Влево)",
    "pipet.next": "Далее (Пробел / Вправо) →",
    "pipet.reset": "Сначала",
    "pipet.progress": "Шаг {cur} из {total}",
    "pipet.done": "Все занятые лунки успешно раскапаны!",
    "pipet.well_info": "Лунка {coord}  |  Образец: {sample}  |  Мишень: {assay}  |  Тип: {role}",
    "pipet.col_strip": "Столбец {col} ({n} лунок)",
    "pipet.row_strip": "Строка {row} ({n} лунок)",
    "pipet.volumes_info": "Внести Master Mix: {mix:.1f} мкл   +   ДНК: {dna:.2f} мкл   +   Вода: {water:.2f} мкл",

    # Statuses & dialogs
    "status.ready": "Готово — {fmt} (занято лунок: {occupied}/{total})",
    "status.saved": "Проект сохранён: {path}",
    "status.loaded": "Проект открыт: {path}",
    "status.exported": "Экспортировано в: {path}",
    "status.smart_filled": "Smart Fill заполнил лунок: {n}",
    "dlg.about.title": "О программе platekit",
    "dlg.about.body": (
        "<b>platekit 1.0</b><br>"
        "Открытый десктопный планировщик ПЦР/секвенирования, "
        "калькулятор Master Mix и нормализации ДНК.<br><br>"
        "Автор: Алексей Дробин (@adrobi)<br>"
        "Лицензия: MIT"
    ),
    "err.title": "Ошибка",
    "err.open_failed": "Не удалось открыть файл: {err}",
    "err.save_failed": "Не удалось сохранить файл: {err}",
}


def detect_system_language() -> str:
    """Detect OS UI language on Windows, Linux or macOS; fall back to 'en' if undetermined."""
    # 1. Check standard POSIX / environment variables
    for env_var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        val = os.environ.get(env_var, "").strip()
        if not val or val.upper() in ("C", "C.UTF-8", "POSIX"):
            continue
        first_token = val.split(":")[0].strip().lower()
        if first_token.startswith(("ru", "russian")):
            return "ru"
        if len(first_token) >= 2 and first_token[:2].isalpha():
            return "en"

    # 2. Check Windows Win32 UI language if running on Windows
    if sys.platform == "win32":
        try:
            windll = getattr(ctypes, "windll", None)
            if windll is not None:
                lang_id = int(windll.kernel32.GetUserDefaultUILanguage())
                # Primary language 0x19 is Russian (LANG_RUSSIAN)
                if (lang_id & 0x3FF) == 0x19:
                    return "ru"
                win_loc = locale.windows_locale.get(lang_id, "").lower()
                if win_loc.startswith("ru"):
                    return "ru"
                if win_loc:
                    return "en"
        except Exception:
            pass

    # 3. Check Python locale
    try:
        loc_name, _ = locale.getlocale()
        if loc_name:
            low = loc_name.lower()
            if low.startswith(("ru", "russian")):
                return "ru"
            if low not in ("c", "posix"):
                return "en"
    except Exception:
        pass

    # 4. Check Qt QLocale if available
    try:
        from PySide6.QtCore import QLocale

        sys_loc = QLocale.system().name().lower()
        if sys_loc.startswith("ru"):
            return "ru"
    except Exception:
        pass

    return "en"


_lang: str = detect_system_language()


def set_language(lang: str | None) -> None:
    global _lang
    if not lang or lang == "auto":
        _lang = detect_system_language()
    elif lang in ("ru", "en"):
        _lang = lang
    else:
        _lang = "en"


def language() -> str:
    return _lang


def tr(key: str, **kwargs) -> str:
    table = RU if _lang == "ru" else EN
    text = table.get(key) or EN.get(key) or key
    return text.format(**kwargs) if kwargs else text
