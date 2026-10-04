from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv, set_key
from PySide6.QtCore import QPointF, QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .runtime import LiveBot


COLORS = {
    "bg": "#080C12", "panel": "#101722", "card": "#141D29", "border": "#223044",
    "text": "#EAF0F7", "muted": "#8290A3", "accent": "#8B6CFF",
    "green": "#29D391", "red": "#FF627D", "amber": "#FFB454",
}


STYLE = f"""
* {{ font-family: Inter, Segoe UI, sans-serif; color: {COLORS['text']}; font-size: 13px; }}
QMainWindow, QWidget#root {{ background: {COLORS['bg']}; }}
QFrame#sidebar {{ background: #0C121B; border-right: 1px solid {COLORS['border']}; }}
QFrame[class="card"] {{ background: {COLORS['card']}; border: 1px solid {COLORS['border']}; border-radius: 14px; }}
QLabel#brand {{ font-size: 22px; font-weight: 800; }}
QLabel#title {{ font-size: 25px; font-weight: 750; }}
QLabel#kpi {{ font-size: 25px; font-weight: 750; }}
QLabel#muted {{ color: {COLORS['muted']}; }}
QLabel#pair {{ font-size: 17px; font-weight: 700; }}
QLabel#price {{ font-size: 22px; font-weight: 750; }}
QPushButton {{ background: #172131; border: 1px solid {COLORS['border']}; border-radius: 9px; padding: 9px 14px; font-weight: 600; }}
QPushButton:hover {{ background: #202D40; }}
QPushButton#primary {{ background: {COLORS['accent']}; border: 0; color: white; }}
QPushButton#primary:hover {{ background: #9A80FF; }}
QPushButton#danger {{ background: #321822; border: 1px solid #64283B; color: #FF8AA0; }}
QPushButton#nav {{ border: 0; background: transparent; text-align: left; padding: 11px 14px; color: {COLORS['muted']}; }}
QPushButton#nav:hover {{ background: #141D29; color: {COLORS['text']}; }}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{ background: #0C131D; border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 8px; min-height: 20px; }}
QComboBox::drop-down {{ border: 0; width: 24px; }}
QTextEdit {{ background: #0B111A; border: 1px solid {COLORS['border']}; border-radius: 12px; padding: 8px; color: #AEBACC; font-family: 'JetBrains Mono', monospace; }}
QTabWidget::pane {{ border: 0; }}
QTabBar::tab {{ background: transparent; color: {COLORS['muted']}; padding: 10px 18px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {COLORS['text']}; border-bottom-color: {COLORS['accent']}; }}
QScrollArea {{ border: 0; background: transparent; }}
"""


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / relative


def config_dir() -> Path:
    candidates = [Path.cwd(), Path(sys.executable).resolve().parent]
    if getattr(sys, "frozen", False) and len(Path(sys.executable).resolve().parents) > 2:
        candidates.append(Path(sys.executable).resolve().parents[2])
    return next((path for path in candidates if (path / ".env.testnet").exists()), Path.cwd())


def env_path(mode: str) -> Path:
    return config_dir() / {"Paper": ".env", "Testnet": ".env.testnet", "Mainnet": ".env.mainnet"}[mode]


def load_mode(mode: str) -> None:
    if mode == "Paper":
        os.environ["BYBIT_ENV"] = "paper"
        os.environ.setdefault("GRIDBOT_SYMBOLS", "BTCUSDT,ADAUSDT,DOGEUSDT")
    else:
        load_dotenv(env_path(mode), override=True)


class Sparkline(QWidget):
    def __init__(self):
        super().__init__()
        self.values: list[float] = []
        self.setMinimumHeight(86)

    def set_values(self, values: list[float]) -> None:
        self.values = values
        self.update()

    def paintEvent(self, event) -> None:
        if len(self.values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bounds = QRectF(4, 8, self.width() - 8, self.height() - 16)
        low, high = min(self.values), max(self.values)
        spread = high - low or 1
        points = [QPointF(
            bounds.left() + i * bounds.width() / (len(self.values) - 1),
            bounds.bottom() - (value - low) / spread * bounds.height(),
        ) for i, value in enumerate(self.values)]
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        fill = QPainterPath(path)
        fill.lineTo(bounds.right(), bounds.bottom())
        fill.lineTo(bounds.left(), bounds.bottom())
        gradient = QLinearGradient(0, bounds.top(), 0, bounds.bottom())
        gradient.setColorAt(0, QColor(139, 108, 255, 75))
        gradient.setColorAt(1, QColor(139, 108, 255, 0))
        painter.fillPath(fill, gradient)
        painter.setPen(QPen(QColor(COLORS["accent"]), 2.2))
        painter.drawPath(path)


class KpiCard(QFrame):
    def __init__(self, title: str, value: str, accent: str = COLORS["text"]):
        super().__init__()
        self.setProperty("class", "card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        label = QLabel(title.upper())
        label.setObjectName("muted")
        self.value = QLabel(value)
        self.value.setObjectName("kpi")
        self.value.setStyleSheet(f"color:{accent}")
        layout.addWidget(label)
        layout.addWidget(self.value)


class PairCard(QFrame):
    def __init__(self, symbol: str):
        super().__init__()
        self.setProperty("class", "card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        top = QHBoxLayout()
        self.symbol = QLabel(symbol)
        self.symbol.setObjectName("pair")
        self.regime = QLabel("ОЖИДАНИЕ")
        self.regime.setAlignment(Qt.AlignCenter)
        self.regime.setFixedSize(94, 34)
        top.addWidget(self.symbol)
        top.addStretch()
        top.addWidget(self.regime)
        self.price = QLabel("—")
        self.price.setObjectName("price")
        self.chart = Sparkline()
        stats = QGridLayout()
        stats.setHorizontalSpacing(12)
        self.adx, self.atr, self.position, self.orders = (QLabel("—") for _ in range(4))
        for col, (name, widget) in enumerate((("ADX", self.adx), ("ATR", self.atr), ("ПОЗИЦИЯ", self.position), ("ОРДЕРА", self.orders))):
            title = QLabel(name)
            title.setObjectName("muted")
            stats.addWidget(title, 0, col)
            stats.addWidget(widget, 1, col)
            stats.setColumnStretch(col, 1)
        layout.addLayout(top)
        layout.addWidget(self.price)
        layout.addWidget(self.chart)
        layout.addLayout(stats)

    def update_data(self, data: dict) -> None:
        self.price.setText(f"{data['price']:,.8g} USDT")
        self.adx.setText(f"{data['adx']:.1f}")
        self.atr.setText(f"{data['atr']:.6g}")
        self.position.setText(f"{data['position']:.6g}")
        self.orders.setText(str(data["orders"]))
        self.chart.set_values(data["closes"])
        if data["ranging"]:
            self.regime.setText("БОКОВИК")
            self.regime.setStyleSheet(f"background:#123128;color:{COLORS['green']};padding:6px;border-radius:9px;font-weight:700")
        else:
            self.regime.setText("ТРЕНД")
            self.regime.setStyleSheet(f"background:#332518;color:{COLORS['amber']};padding:6px;border-radius:9px;font-weight:700")


class SnapshotThread(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, mode: str):
        super().__init__()
        self.mode = mode

    def run(self) -> None:
        try:
            load_mode(self.mode)
            self.ready.emit(LiveBot().dashboard_snapshot())
        except Exception as exc:
            self.failed.emit(str(exc))


class BotThread(QThread):
    message = Signal(str)
    failed = Signal(str)

    def __init__(self, mode: str, execute: bool, confirm_real: bool):
        super().__init__()
        self.mode, self.execute, self.confirm_real = mode, execute, confirm_real
        self.stop_event = threading.Event()
        self.bot: LiveBot | None = None

    def run(self) -> None:
        try:
            load_mode(self.mode)
            self.bot = LiveBot(execute=self.execute, confirm_real=self.confirm_real)
            self.message.emit(f"{self.mode}: бот запущен")
            self.bot.run_forever(self.stop_event)
            if self.execute:
                self.bot.stop(flatten=False)
            self.message.emit(f"{self.mode}: бот остановлен")
        except Exception as exc:
            self.failed.emit(str(exc))

    def request_stop(self) -> None:
        self.stop_event.set()


class EmergencyThread(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, mode: str, confirm_real: bool):
        super().__init__()
        self.mode, self.confirm_real = mode, confirm_real

    def run(self) -> None:
        try:
            load_mode(self.mode)
            bot = LiveBot(execute=True, confirm_real=self.confirm_real)
            bot.stop(flatten=True)
            self.done.emit(f"{self.mode}: ордера отменены, позиции закрыты")
        except Exception as exc:
            self.failed.emit(str(exc))


class ConfirmMainnet(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Подтверждение реального счёта")
        layout = QVBoxLayout(self)
        warning = QLabel("Режим реальных денег может привести к потере всего депозита.\nВведите MAINNET для продолжения.")
        warning.setStyleSheet(f"color:{COLORS['red']};font-weight:700")
        self.input = QLineEdit()
        self.input.setPlaceholderText("MAINNET")
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(warning)
        layout.addWidget(self.input)
        layout.addWidget(buttons)

    def accepted_phrase(self) -> bool:
        return self.exec() == QDialog.Accepted and self.input.text() == "MAINNET"


class MainWindow(QMainWindow):
    def __init__(self, preview: bool = False):
        super().__init__()
        self.setWindowTitle("GridPilot — торговый бот Bybit")
        self.setWindowIcon(QIcon(str(resource_path("assets/gridpilot.svg"))))
        self.resize(1360, 860)
        self.setMinimumSize(1080, 700)
        self.preview = preview
        self.snapshot_thread: SnapshotThread | None = None
        self.bot_thread: BotThread | None = None
        self.emergency_thread: EmergencyThread | None = None
        self.pair_cards: dict[str, PairCard] = {}

        root = QWidget(objectName="root")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._sidebar())
        shell.addWidget(self._content(), 1)
        for button, index in zip(self.nav_buttons, (0, 1, 1, 2)):
            button.clicked.connect(lambda checked=False, tab=index: self.tabs.setCurrentIndex(tab))
        self.setCentralWidget(root)
        self.setStyleSheet(STYLE)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        if preview:
            QTimer.singleShot(100, self.preview_data)
        else:
            self.timer.start(15_000)
            QTimer.singleShot(200, self.refresh)

    def _sidebar(self) -> QFrame:
        side = QFrame(objectName="sidebar")
        side.setFixedWidth(230)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(18, 22, 18, 18)
        brand = QLabel("◆  GRIDPILOT", objectName="brand")
        brand.setStyleSheet(f"color:{COLORS['accent']}")
        subtitle = QLabel("АВТОМАТИЗАЦИЯ BYBIT")
        subtitle.setObjectName("muted")
        layout.addWidget(brand)
        layout.addWidget(subtitle)
        layout.addSpacing(28)
        self.nav_buttons = []
        for text in ("▦   Обзор", "⌁   Стратегия", "⚙   Управление риском", "≡   Журнал событий"):
            button = QPushButton(text, objectName="nav")
            self.nav_buttons.append(button)
            layout.addWidget(button)
        layout.addStretch()
        safety = QLabel("ЗАЩИТА MAINNET\nДвойное подтверждение")
        safety.setWordWrap(True)
        safety.setObjectName("muted")
        safety.setStyleSheet(f"background:#111925;border:1px solid {COLORS['border']};border-radius:10px;padding:12px;color:{COLORS['muted']}")
        layout.addWidget(safety)
        return side

    def _content(self) -> QWidget:
        area = QWidget()
        layout = QVBoxLayout(area)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.addWidget(QLabel("Обзор торговли", objectName="title"))
        self.updated = QLabel("Подключение…", objectName="muted")
        title_box.addWidget(self.updated)
        header.addLayout(title_box)
        header.addStretch()
        self.mode = QComboBox()
        self.mode.addItem("Симуляция", "Paper")
        self.mode.addItem("Тестовый счёт", "Testnet")
        self.mode.addItem("Реальный счёт", "Mainnet")
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.clicked.connect(self.refresh)
        self.start_button = QPushButton("Запустить", objectName="primary")
        self.start_button.clicked.connect(self.start_bot)
        self.stop_button = QPushButton("Остановить")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_bot)
        self.emergency = QPushButton("Аварийно закрыть", objectName="danger")
        self.emergency.clicked.connect(self.emergency_stop)
        for widget in (self.mode, self.refresh_button, self.start_button, self.stop_button, self.emergency):
            header.addWidget(widget)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._dashboard(), "Обзор")
        self.tabs.addTab(self._settings(), "Стратегия и риск")
        self.tabs.addTab(self._logs(), "События")
        layout.addWidget(self.tabs, 1)
        return area

    def _dashboard(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        kpis = QHBoxLayout()
        self.equity = KpiCard("Общий баланс", "— USDT")
        self.active = KpiCard("Состояние бота", "ОСТАНОВЛЕН", COLORS["muted"])
        self.positions = KpiCard("Открытые позиции", "—")
        self.order_count = KpiCard("Ордера сетки", "—")
        for card in (self.equity, self.active, self.positions, self.order_count):
            kpis.addWidget(card)
        layout.addLayout(kpis)
        cards = QHBoxLayout()
        cards.setSpacing(12)
        for symbol in ("BTCUSDT", "ADAUSDT", "DOGEUSDT"):
            card = PairCard(symbol)
            self.pair_cards[symbol] = card
            cards.addWidget(card)
        layout.addLayout(cards, 1)
        return page

    def _settings(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 18, 0, 0)
        fields = (
            ("Количество уровней сетки", "GRIDBOT_LEVELS", QSpinBox(), 5),
            ("Расстояние в ATR", "GRIDBOT_SPACING_ATR", QDoubleSpinBox(), 0.5),
            ("Доля капитала, %", "GRIDBOT_MAX_POSITION_FRACTION", QDoubleSpinBox(), 45.0),
            ("Максимальная просадка, %", "GRIDBOT_MAX_DRAWDOWN", QDoubleSpinBox(), 10.0),
            ("Дневной лимит убытка, %", "GRIDBOT_MAX_DAILY_LOSS", QDoubleSpinBox(), 3.0),
        )
        self.settings_fields = {}
        for row, (label, key, field, default) in enumerate(fields):
            field.setRange(1, 100) if isinstance(field, QSpinBox) else field.setRange(0.01, 100)
            field.setDecimals(2) if isinstance(field, QDoubleSpinBox) else None
            field.setValue(default)
            layout.addWidget(QLabel(label), row, 0)
            layout.addWidget(field, row, 1)
            self.settings_fields[key] = field
        save = QPushButton("Сохранить настройки", objectName="primary")
        save.clicked.connect(self.save_settings)
        layout.addWidget(save, len(fields), 1)
        note = QLabel("Лимит капитала делится между выбранными парами. Изменения применятся на следующем цикле сверки.")
        note.setObjectName("muted")
        layout.addWidget(note, len(fields) + 1, 0, 1, 2)
        layout.setColumnStretch(2, 1)
        layout.setRowStretch(len(fields) + 2, 1)
        return page

    def _logs(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 18, 0, 0)
        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setPlainText("GridPilot готов. API-ключи и секреты здесь никогда не отображаются.\n")
        layout.addWidget(self.logs)
        return page

    def log(self, message: str) -> None:
        self.logs.append(message)

    def mode_changed(self, index: int) -> None:
        mode = self.mode.currentData()
        color = COLORS["red"] if mode == "Mainnet" else COLORS["green"] if mode == "Testnet" else COLORS["accent"]
        self.mode.setStyleSheet(f"color:{color};font-weight:700")
        names = {"Paper": "Симуляция", "Testnet": "Тестовый счёт", "Mainnet": "Реальный счёт"}
        self.log(f"Выбран режим: {names[mode]}")
        self.load_settings(mode)
        self.refresh()

    def load_settings(self, mode: str) -> None:
        if mode != "Paper":
            load_mode(mode)
        if not hasattr(self, "settings_fields"):
            return
        defaults = {
            "GRIDBOT_LEVELS": 5, "GRIDBOT_SPACING_ATR": 0.5,
            "GRIDBOT_MAX_POSITION_FRACTION": 0.45, "GRIDBOT_MAX_DRAWDOWN": 0.10,
            "GRIDBOT_MAX_DAILY_LOSS": 0.03,
        }
        for key, field in self.settings_fields.items():
            value = float(os.getenv(key, defaults[key]))
            if key in {"GRIDBOT_MAX_POSITION_FRACTION", "GRIDBOT_MAX_DRAWDOWN", "GRIDBOT_MAX_DAILY_LOSS"}:
                value *= 100
            field.setValue(value)

    def refresh(self) -> None:
        if self.preview or (self.snapshot_thread and self.snapshot_thread.isRunning()):
            return
        self.refresh_button.setEnabled(False)
        self.snapshot_thread = SnapshotThread(self.mode.currentData())
        self.snapshot_thread.ready.connect(self.apply_snapshot)
        self.snapshot_thread.failed.connect(self.refresh_failed)
        self.snapshot_thread.finished.connect(lambda: self.refresh_button.setEnabled(True))
        self.snapshot_thread.start()

    def apply_snapshot(self, snapshot: dict) -> None:
        self.equity.value.setText(f"{snapshot['equity']:,.2f} USDT")
        environment = {"paper": "СИМУЛЯЦИЯ", "testnet": "ТЕСТОВЫЙ СЧЁТ", "demo": "ДЕМО", "mainnet": "РЕАЛЬНЫЙ СЧЁТ"}.get(snapshot["environment"], snapshot["environment"].upper())
        self.updated.setText(f"{environment} • Обновлено {snapshot['updated']}")
        self.positions.value.setText(str(sum(pair["position"] != 0 for pair in snapshot["pairs"])))
        self.order_count.value.setText(str(sum(pair["orders"] for pair in snapshot["pairs"])))
        for pair in snapshot["pairs"]:
            if pair["symbol"] in self.pair_cards:
                self.pair_cards[pair["symbol"]].update_data(pair)
        if snapshot["halted"]:
            self.active.value.setText("АВТОСТОП")
            self.active.value.setStyleSheet(f"color:{COLORS['red']}")

    def refresh_failed(self, message: str) -> None:
        self.updated.setText("Ошибка подключения")
        self.log(f"ОШИБКА: {message}")

    def start_bot(self) -> None:
        if self.bot_thread and self.bot_thread.isRunning():
            return
        mode = self.mode.currentData()
        execute, confirm = mode != "Paper", False
        if mode == "Mainnet":
            confirm = ConfirmMainnet(self).accepted_phrase()
            if not confirm:
                return
        self.bot_thread = BotThread(mode, execute, confirm)
        self.bot_thread.message.connect(self.log)
        self.bot_thread.failed.connect(self.bot_failed)
        self.bot_thread.finished.connect(self.bot_finished)
        self.bot_thread.start()
        self.active.value.setText("РАБОТАЕТ")
        self.active.value.setStyleSheet(f"color:{COLORS['green']}")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_bot(self) -> None:
        if self.bot_thread:
            self.bot_thread.request_stop()
            self.stop_button.setEnabled(False)

    def bot_failed(self, message: str) -> None:
        self.log(f"ОШИБКА БОТА: {message}")
        QMessageBox.critical(self, "Ошибка бота", message)

    def bot_finished(self) -> None:
        self.active.value.setText("ОСТАНОВЛЕН")
        self.active.value.setStyleSheet(f"color:{COLORS['muted']}")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.refresh()

    def emergency_stop(self) -> None:
        mode = self.mode.currentData()
        if mode == "Paper":
            self.stop_bot()
            return
        answer = QMessageBox.warning(
            self, "Аварийное закрытие", "Отменить ордера бота и закрыть все позиции аккаунта по рынку?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.stop_bot()
        confirm = mode != "Mainnet" or ConfirmMainnet(self).accepted_phrase()
        if not confirm:
            return
        self.emergency.setEnabled(False)
        self.emergency_thread = EmergencyThread(mode, confirm)
        self.emergency_thread.done.connect(self.log)
        self.emergency_thread.failed.connect(self.bot_failed)
        self.emergency_thread.finished.connect(lambda: (self.emergency.setEnabled(True), self.refresh()))
        self.emergency_thread.start()

    def save_settings(self) -> None:
        mode = self.mode.currentData()
        if mode == "Paper":
            QMessageBox.information(self, "Настройки симуляции", "Выберите тестовый или реальный счёт для сохранения файла настроек.")
            return
        path = env_path(mode)
        for key, field in self.settings_fields.items():
            value = field.value()
            if key in {"GRIDBOT_MAX_POSITION_FRACTION", "GRIDBOT_MAX_DRAWDOWN", "GRIDBOT_MAX_DAILY_LOSS"}:
                value /= 100
            set_key(str(path), key, str(value))
        self.log(f"Настройки сохранены в {path.name}")

    def preview_data(self) -> None:
        sample = {
            "environment": "paper", "equity": 10_248.52, "updated": "18:42:09 UTC", "halted": None,
            "pairs": [],
        }
        import math
        for i, (symbol, price, ranging) in enumerate((("BTCUSDT", 64281.4, True), ("ADAUSDT", 0.3562, True), ("DOGEUSDT", 0.1094, False))):
            closes = [price * (1 + 0.012 * math.sin(n / 5 + i) + n / 8000) for n in range(50)]
            sample["pairs"].append({"symbol": symbol, "price": closes[-1], "adx": 18.4 + i * 7,
                "atr": price * 0.008, "ranging": ranging, "position": 0 if i != 1 else 125,
                "orders": 10 if ranging else 0, "closes": closes})
        self.apply_snapshot(sample)


def main() -> None:
    preview = "--preview" in sys.argv
    app = QApplication(sys.argv)
    app.setApplicationName("GridPilot")
    app.setWindowIcon(QIcon(str(resource_path("assets/gridpilot.svg"))))
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow(preview=preview)
    window.show()
    if "--screenshot" in sys.argv:
        output = Path.cwd() / "gridpilot-preview.png"
        QTimer.singleShot(800, lambda: (window.grab().save(str(output)), print(output), app.quit()))
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
