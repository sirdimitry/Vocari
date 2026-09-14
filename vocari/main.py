"""Entry point: loads config + avatar model and shows the transparent overlay window."""
from __future__ import annotations

import signal
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from vocari.__version__ import __version__
from vocari.branding import app_icon
from vocari.chat.base import ChatMessage
from vocari.chat.filters import CooldownTracker, extract_command_text, find_blacklisted_word, has_access
from vocari.config.settings import AppConfig, OverlayConfig
from vocari.hotkey import GlobalHotkeyManager
from vocari.logging_setup import get_logger, setup_logging
from vocari.paths import app_root
from vocari.runtime_deps import ensure_all_on_path
from vocari.rendering.model import AvatarModel, load_model
from vocari.rendering.overlay_window import MAX_SCALE, MIN_SCALE, OverlayWindow
from vocari.rendering.stage import Stage
from vocari.tts.audio_player import AudioPlayer
from vocari.tts.edge_provider import EdgeTTSProvider
from vocari.tts.service import enforce_length_limit
from vocari.tts.silero_provider import SileroTTSProvider
from vocari.tts.tts_queue import TTSQueue
from vocari.twitch.bot_controller import TwitchBotController
from vocari.ui.log_window import LogWindow
from vocari.ui.settings_window import SettingsWindow
from vocari.ui.tray_icon import TrayController

PROJECT_ROOT = app_root()

logger = get_logger("main")

# First-run defaults (see OverlayConfig's -1/0.0 sentinels): sized against
# the user's actual screen instead of the model's native PNG pixel size, so
# e.g. a 1280px-tall canvas doesn't default to dwarfing a 1080p monitor.
TARGET_AVATAR_HEIGHT_FRACTION = 0.45  # avatar height, as a fraction of screen height
TARGET_STAGE_WIDTH_FRACTION = 0.9  # full stage width (speaker + queue + exit corridor), as a fraction of screen width
EDGE_MARGIN_PX = 20


def _apply_screen_defaults(config: AppConfig, model: AvatarModel) -> None:
    """Resolves scale/position "not yet set" sentinels against the primary
    screen's resolution, once. Only touches whichever of scale/pos_x/pos_y is
    still at its sentinel — once the user drags/scrolls/types a real value
    and it's saved to config.json, this leaves it alone on every later run."""
    overlay = config.overlay
    needs_scale = overlay.scale <= 0
    needs_position = overlay.pos_x < 0 or overlay.pos_y < 0
    if not needs_scale and not needs_position:
        return

    screen = QApplication.primaryScreen()
    if screen is None:  # headless/unusual environment — fall back to old hardcoded defaults
        if needs_scale:
            overlay.scale = 1.0
        if needs_position:
            overlay.pos_x, overlay.pos_y = 100, 100
        return

    screen_size = screen.availableGeometry().size()
    canvas_w, canvas_h = model.canvas_size
    # Stage owns the queue/entry-buffer geometry ratios — reuse them here
    # instead of duplicating the math, so this stays in sync automatically.
    stage_origin_x = Stage(canvas_width=canvas_w).stage_origin_x

    if needs_scale:
        scale_by_height = screen_size.height() * TARGET_AVATAR_HEIGHT_FRACTION / canvas_h
        scale_by_width = screen_size.width() * TARGET_STAGE_WIDTH_FRACTION / (stage_origin_x + canvas_w)
        overlay.scale = max(MIN_SCALE, min(MAX_SCALE, min(scale_by_height, scale_by_width)))
        logger.info(
            "Экран %dx%d: масштаб по умолчанию — %.3f",
            screen_size.width(), screen_size.height(), overlay.scale,
        )

    if needs_position:
        # As far left as the whole stage (queue + entrance/exit corridor)
        # still fits on screen, bottom-anchored — a common overlay placement.
        overlay.pos_x = round(stage_origin_x * overlay.scale) + EDGE_MARGIN_PX
        overlay.pos_y = max(
            EDGE_MARGIN_PX, round(screen_size.height() - canvas_h * overlay.scale - EDGE_MARGIN_PX)
        )


def main() -> None:
    # Without an explicit AppUserModelID, Windows groups/represents a
    # python.exe-hosted GUI app in the taskbar under python.exe's own icon
    # (a Python logo) instead of whatever the window itself sets via
    # setWindowIcon() — a well-known quirk for any Python GUI app run from
    # source rather than as its own frozen .exe (which doesn't need this:
    # it already has its own real PE icon resource, see vocari.spec).
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Vocari.Vocari.App")
        except OSError:
            pass

    # Before anything else — makes a previously-downloaded torch (see
    # runtime_deps.py / Settings -> Silero) importable again this run. A
    # dev venv with torch already installed the normal way is unaffected;
    # this only ever adds a path, never removes torch from view.
    ensure_all_on_path()

    log_file = setup_logging(PROJECT_ROOT)

    app = QApplication(sys.argv)
    # Fallback icon for anything Windows shows before/without a specific
    # window's own setWindowIcon() (e.g. taskbar grouping, Alt+Tab before a
    # window's finished loading) — each top-level window also sets its own
    # via vocari.branding.app_icon(), this just covers the gap between them.
    app.setWindowIcon(app_icon())
    # The overlay window is frameless; hiding it must not quit the app — only
    # the tray icon's "Выход" should.
    app.setQuitOnLastWindowClosed(False)

    # Ctrl+C in a terminal otherwise raises KeyboardInterrupt inside whatever
    # Qt callback happens to be running (paintEvent, a timer tick, ...),
    # which can leave things like an in-progress QPainter half-finished.
    # Route it through a clean app.quit() instead.
    signal.signal(signal.SIGINT, lambda *_args: app.quit())

    logger.info("Vocari v%s запускается", __version__)

    config = AppConfig.load()
    model_dir = PROJECT_ROOT / config.overlay.model_path
    logger.info("Загрузка модели из %s", model_dir)
    try:
        model = load_model(model_dir)
    except Exception:
        # The saved model_path can point at a folder that's since been
        # deleted (moved away by hand, or removed via Settings → Модель) —
        # without this, a stale config.json made the app unable to start at
        # all. Fall back to the bundled default and fix the config so this
        # doesn't recur on the next launch too.
        default_path = OverlayConfig().model_path
        logger.exception(
            "Не удалось загрузить модель из %s, откатываюсь на %s", model_dir, default_path
        )
        config.overlay.model_path = default_path
        config.save()
        model_dir = PROJECT_ROOT / default_path
        model = load_model(model_dir)
    logger.info(
        "Модель '%s' загружена: %d базовых слоёв, состояния: %s",
        model.name,
        len(model.base_layers),
        ", ".join(model.states.keys()) or "нет",
    )

    _apply_screen_defaults(config, model)

    window = OverlayWindow(model, config.overlay, config.render, config.bubble)
    # Preload every bundled model so random mode can mix characters on stage.
    available = []
    for folder in sorted((PROJECT_ROOT / "assets" / "models").iterdir()):
        if not (folder / "model.json").exists():
            continue
        try:
            available.append(load_model(folder))
        except Exception:
            logger.exception("Не удалось загрузить модель из %s", folder)
    window.set_available_models(available)
    window.set_random_model(config.overlay.random_model)
    window.set_random_pool(config.overlay.random_pool)
    window.set_model_weights(config.overlay.model_weights)
    window.set_user_model_bindings(config.overlay.user_model_bindings)
    logger.info("Доступные модели: %s", ", ".join(m.name for m in available) or "—")
    window.show()

    def on_model_selected(model_path: str) -> None:
        try:
            new_model = load_model(PROJECT_ROOT / model_path)
        except Exception:
            logger.exception("Не удалось загрузить модель %s", model_path)
            return
        window.set_model(new_model)
        settings_window.model_tab.set_model(new_model)
        logger.info("Активная модель: %s", new_model.name)

    def on_random_model_toggled(enabled: bool) -> None:
        window.set_random_model(enabled)
        logger.info("Случайный аватар: %s", "включён" if enabled else "выключен")

    def on_random_pool_changed(names: list[str]) -> None:
        window.set_random_pool(names)
        logger.info("Участвуют в случайном выборе: %s", ", ".join(names) or "все")

    def on_model_weights_changed(weights: dict[str, float]) -> None:
        window.set_model_weights(weights)

    def on_bindings_changed(bindings: dict[str, str]) -> None:
        window.set_user_model_bindings(bindings)

    def on_model_deleted(name: str) -> None:
        # model_tab.py already pruned config.overlay.model_weights/
        # user_model_bindings for this name before calling here - push that
        # forward to the live overlay and to the "Ники" tab's own widgets so
        # nothing keeps offering a model that's gone (see bindings_tab.py's
        # refresh_models() docstring for why this matters).
        window.set_model_weights(config.overlay.model_weights)
        window.set_user_model_bindings(config.overlay.user_model_bindings)
        settings_window.bindings_tab.refresh_models()
        logger.info("Модель '%s' удалена: привязки и веса очищены", name)

    def on_model_imported(model_dir: Path) -> None:
        try:
            new_model = load_model(model_dir)
        except Exception:
            logger.exception("Не удалось загрузить импортированную модель из %s", model_dir)
            return
        window.set_model(new_model)
        settings_window.model_tab.set_model(new_model)
        settings_window.bindings_tab.refresh_models()
        logger.info("Оверлей обновлён: модель '%s'", new_model.name)

    tts_providers = {"edge": EdgeTTSProvider(), "silero": SileroTTSProvider()}
    audio_player = AudioPlayer()
    tts_queue = TTSQueue(config, tts_providers, audio_player, window)

    hotkey_manager = GlobalHotkeyManager(app)
    if config.hotkey.skip_message:
        if not hotkey_manager.set_binding(config.hotkey.skip_message):
            logger.warning("Не удалось зарегистрировать сохранённый хоткей пропуска: %s", config.hotkey.skip_message)
    # skip_current (not audio_player.skip): the hotkey has to interrupt the
    # speaker whatever it's doing — mid-word, waiting on synthesis, or still
    # sliding in — and send it off stage with the normal exit animation.
    hotkey_manager.triggered.connect(tts_queue.skip_current)

    def on_skip_hotkey_changed(sequence_text: str) -> bool:
        ok = hotkey_manager.set_binding(sequence_text)
        if ok:
            config.hotkey.skip_message = sequence_text
            config.save()
            logger.info("Хоткей пропуска фразы: %s", sequence_text or "выключен")
        return ok

    twitch_bot = TwitchBotController(config.twitch)
    cooldown_tracker = CooldownTracker()

    def on_chat_message(message: ChatMessage) -> None:
        command_text = extract_command_text(message.text, config.twitch.command_prefix)
        if not command_text:
            return
        if not has_access(message, config.twitch):
            logger.info("Twitch: %s — нет доступа к команде (фильтр подписки/VIP/модератора)", message.display_name)
            return
        if not cooldown_tracker.check_and_record(message.username, config.twitch.cooldown_seconds):
            logger.info("Twitch: %s — кулдаун", message.display_name)
            return
        blocked_word = find_blacklisted_word(command_text, config.twitch.blacklist_words)
        if blocked_word:
            logger.info("Twitch: %s — заблокировано слово '%s'", message.display_name, blocked_word)
            return
        text, truncated = enforce_length_limit(command_text, config.tts)
        logger.info(
            "Twitch !tts от %s: '%s'%s", message.display_name, text, " (обрезано)" if truncated else ""
        )
        # Lets Settings -> Ники offer this nick for a model binding right
        # away, mid-stream, instead of requiring it to be typed by hand -
        # add_known_nick() itself no-ops for a nick already on the list.
        settings_window.bindings_tab.add_known_nick(message.display_name)
        tts_queue.enqueue(text, message.display_name)

    twitch_bot.message_received.connect(on_chat_message)

    log_window = LogWindow(log_file)
    settings_window = SettingsWindow(
        config,
        model,
        on_model_imported,
        window.set_sway_enabled,
        window.set_always_on_top,
        window.set_position,
        window.set_scale,
        window.set_entrance_from_right,
        window.stage.set_exit_speed,
        on_model_selected,
        on_random_model_toggled,
        on_random_pool_changed,
        on_model_deleted,
        on_bindings_changed,
        on_model_weights_changed,
        on_skip_hotkey_changed,
        window.apply_bubble_settings,
        tts_providers,
        tts_queue,
        twitch_bot,
    )
    tray = TrayController(window, app, log_window, settings_window, tts_queue)  # noqa: F841

    def on_quit() -> None:
        logger.info("Vocari завершает работу")
        twitch_bot.stop()
        audio_player.stop()
        hotkey_manager.shutdown()
        window.sync_geometry_to_config()
        config.save()

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
