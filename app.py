import ctypes
import io
import sys
import threading
import time
import numpy as np
import pyperclip
import pyttsx3
import scipy.io.wavfile as wav
import sounddevice as sd
import speech_recognition as sr
from PyQt6.QtCore import QPoint, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QFontMetrics, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def release_stuck_keys():
    VK_CONTROL = 0x11
    VK_MENU = 0x12
    VK_SHIFT = 0x10
    KEYEVENTF_KEYUP = 0x0002

    try:
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
    except (KeyboardInterrupt, Exception):
        pass


def send_ctrl_c_safe():
    VK_CONTROL = 0x11
    VK_C = 0x43
    KEYEVENTF_KEYUP = 0x0002

    try:
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_C, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        release_stuck_keys()


class SpeechWorker(QThread):
    finished_signal = pyqtSignal(str)

    def __init__(self, audio_data, sample_rate):
        super().__init__()
        self.audio_data = audio_data
        self.sample_rate = sample_rate

    def run(self):
        recognizer = sr.Recognizer()
        try:
            byte_io = io.BytesIO()
            wav.write(byte_io, self.sample_rate, self.audio_data)
            byte_io.seek(0)

            with sr.AudioFile(byte_io) as source:
                audio = recognizer.record(source)
                text = recognizer.recognize_google(audio)
                self.finished_signal.emit(text)
        except sr.UnknownValueError:
            self.finished_signal.emit(
                "Could not understand audio. Please speak clearly."
            )
        except sr.RequestError:
            self.finished_signal.emit("Speech recognition service offline.")
        except Exception as e:
            self.finished_signal.emit(f"Microphone error: {str(e)}")


class DraggableButton(QPushButton):
    """Draggable button that moves the logo and updates the options menu position synchronously."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.drag_position = QPoint()
        self.is_dragging = False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self.drag_position = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.window().move(new_pos)

            main_win = self.window()
            if (
                hasattr(main_win, "popup_menu")
                and main_win.popup_menu
                and main_win.popup_menu.isVisible()
            ):
                main_win.update_popup_position()

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_dragging:
                event.accept()
                return
        super().mouseReleaseEvent(event)


class DynamicStackedWidget(QStackedWidget):
    """Stacked widget that reports its sizeHint dynamically based on the current page."""

    def sizeHint(self):
        current = self.currentWidget()
        if current:
            return current.sizeHint()
        return super().sizeHint()


class MenuPopupWindow(QWidget):
    """Popup window holding the options menu inside a curved borderless container."""

    def __init__(self, parent_floating_widget):
        super().__init__(
            flags=Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SubWindow
        )
        self.floating_widget = parent_floating_widget
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setStyleSheet(
            """
            QWidget#MainCard {
                background-color: #12131C;
                border: none;
                border-radius: 12px;
            }
            QPushButton {
                background-color: #1E1F2C;
                color: #FFD700;
                border: 1px solid #2E2F3E;
                border-radius: 8px;
                padding: 6px 10px;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #2E2F3E;
            }
            QPushButton:disabled {
                background-color: #141520;
                color: #666666;
            }
            QPushButton[selected="true"] {
                background-color: #FFD700;
                color: #12131C;
                border: 1px solid #FFD700;
            }
            QTextEdit {
                background-color: #1E1F2C;
                color: #FFFFFF;
                border: 1px solid #FFD700;
                border-radius: 6px;
                padding: 6px;
                font-size: 13px;
            }
            QLabel {
                color: #FFD700;
                font-weight: bold;
            }
        """
        )

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSizeConstraint(
            QVBoxLayout.SizeConstraint.SetFixedSize
        )

        self.container = QWidget(self)
        self.container.setObjectName("MainCard")
        outer_layout.addWidget(self.container)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(8, 6, 8, 8)
        container_layout.setSpacing(5)
        container_layout.setSizeConstraint(
            QVBoxLayout.SizeConstraint.SetFixedSize
        )

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
                color: #FFD700;
                font-size: 12px;
                font-weight: bold;
                padding: 0px;
                text-align: center;
            }
            QPushButton:hover {
                color: #FF4D4D;
                background-color: transparent;
            }
        """
        )
        close_btn.clicked.connect(self.floating_widget.quit_app)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        container_layout.addLayout(header_layout)

        self.stacked_widget = DynamicStackedWidget()
        container_layout.addWidget(self.stacked_widget)

        self.page_main = self.floating_widget.create_main_page()
        self.page_text_options = (
            self.floating_widget.create_text_options_page()
        )
        self.page_select_text = (
            self.floating_widget.create_select_text_page()
        )
        self.page_custom_text = (
            self.floating_widget.create_custom_text_page()
        )
        self.page_speech_options = (
            self.floating_widget.create_speech_options_page()
        )
        self.page_more_settings = (
            self.floating_widget.create_more_settings_page()
        )

        self.stacked_widget.addWidget(self.page_main)
        self.stacked_widget.addWidget(self.page_text_options)
        self.stacked_widget.addWidget(self.page_select_text)
        self.stacked_widget.addWidget(self.page_custom_text)
        self.stacked_widget.addWidget(self.page_speech_options)
        self.stacked_widget.addWidget(self.page_more_settings)

        self.stacked_widget.currentChanged.connect(self.adjust_menu_size)

    def adjust_menu_size(self):
        self.adjustSize()
        self.floating_widget.update_popup_position()


class FloatingWidget(QWidget):

    return_home_signal = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.selected_voice_id = None
        self.speech_rate = 140
        self.is_reading = False

        self.is_recording = False
        self.recorded_chunks = []
        self.sample_rate = 44100
        self.stream = None
        self.popup_menu = None
        self.voice_buttons = {}

        self.return_home_signal.connect(self.go_to_home)

        try:
            temp_engine = pyttsx3.init()
            voices = temp_engine.getProperty("voices")
            if voices:
                self.selected_voice_id = voices[0].id
            del temp_engine
        except Exception:
            pass

        self.init_ui()
        self.setup_system_tray()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(60, 60)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.icon_button = DraggableButton("", self)
        self.icon_button.setFixedSize(60, 60)
        self.icon_button.setStyleSheet(
            """
            QPushButton {
                background-color: #C8102E;
                border: 3px solid #FFD700;
                border-radius: 30px;
            }
            QPushButton:hover {
                background-color: #E60000;
            }
        """
        )

        icon = QIcon("ironman.png")
        if not icon.isNull():
            self.icon_button.setIcon(icon)
            self.icon_button.setIconSize(self.icon_button.size())
        else:
            self.icon_button.setText("🦾")

        self.icon_button.clicked.connect(self.toggle_menu)
        main_layout.addWidget(self.icon_button)

        self.popup_menu = MenuPopupWindow(self)
        self.popup_menu.adjust_menu_size()

        screen = QApplication.primaryScreen().availableGeometry()
        pos_x = screen.x() + screen.width() - 80
        pos_y = screen.y() + screen.height() - 80
        self.move(pos_x, pos_y)

    def setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)

        icon = QIcon("ironman.png")
        if icon.isNull():
            icon = self.style().standardIcon(
                QStyle.StandardPixmap.SP_ComputerIcon
            )

        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()
        show_action = QAction("Show Icon / Menu", self)
        quit_action = QAction("Quit App", self)

        show_action.triggered.connect(self.show_icon)
        quit_action.triggered.connect(self.quit_app)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(lambda: self.show_icon())
        self.tray_icon.show()

    def show_icon(self):
        self.showNormal()
        self.activateWindow()

    def hide_icon(self):
        if self.popup_menu:
            self.popup_menu.hide()
        self.hide()

    def quit_app(self):
        release_stuck_keys()
        self.tray_icon.hide()
        QApplication.instance().quit()

    def go_to_home(self):
        self.reset_speech_ui()
        if self.popup_menu:
            self.popup_menu.stacked_widget.setCurrentWidget(
                self.popup_menu.page_main
            )

    def update_popup_position(self):
        if not self.popup_menu:
            return
        logo_geom = self.geometry()
        popup_size = self.popup_menu.sizeHint()

        pos_x = logo_geom.x() - popup_size.width() - 8
        pos_y = logo_geom.y() + logo_geom.height() - popup_size.height()

        self.popup_menu.move(pos_x, pos_y)

    def toggle_menu(self):
        if self.popup_menu and self.popup_menu.isVisible():
            self.popup_menu.hide()
        else:
            self.go_to_home()
            self.update_popup_position()
            if self.popup_menu:
                self.popup_menu.show()

    def show_centered_message(self, icon, title, text):
        msg = QMessageBox(self)
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        screen_geometry = QApplication.primaryScreen().geometry()
        msg.adjustSize()
        x = screen_geometry.x() + (screen_geometry.width() - msg.width()) // 2
        y = screen_geometry.y() + (screen_geometry.height() - msg.height()) // 2
        msg.move(x, y)

        msg.exec()

    def create_main_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        btn_texts = [
            "💬 Read Text ▶",
            "🎙 Record Speech ▶",
            "🙈 Hide Icon",
            "⚙ More Settings...",
        ]

        font_metrics = QFontMetrics(page.font())
        max_text_width = max(
            font_metrics.horizontalAdvance(text) for text in btn_texts
        )
        btn_width = max_text_width + 25

        buttons = []
        for text in btn_texts:
            btn = QPushButton(text)
            btn.setFixedWidth(btn_width)
            buttons.append(btn)
            layout.addWidget(btn)

        buttons[0].clicked.connect(
            lambda: self.popup_menu.stacked_widget.setCurrentWidget(
                self.popup_menu.page_text_options
            )
        )
        buttons[1].clicked.connect(
            lambda: self.popup_menu.stacked_widget.setCurrentWidget(
                self.popup_menu.page_speech_options
            )
        )
        buttons[2].clicked.connect(self.hide_icon)
        buttons[3].clicked.connect(
            lambda: self.popup_menu.stacked_widget.setCurrentWidget(
                self.popup_menu.page_more_settings
            )
        )

        return page

    def create_text_options_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        btn_select = QPushButton("Read Selected Text")
        btn_custom = QPushButton("Enter Custom Text")
        btn_back = QPushButton("◀ Back")

        font_metrics = QFontMetrics(page.font())
        btn_width = (
            font_metrics.horizontalAdvance("Read Selected Text") + 25
        )

        btn_select.setFixedWidth(btn_width)
        btn_custom.setFixedWidth(btn_width)
        btn_back.setFixedWidth(btn_width)

        btn_select.clicked.connect(
            lambda: self.popup_menu.stacked_widget.setCurrentWidget(
                self.popup_menu.page_select_text
            )
        )
        btn_custom.clicked.connect(
            lambda: self.popup_menu.stacked_widget.setCurrentWidget(
                self.popup_menu.page_custom_text
            )
        )
        btn_back.clicked.connect(self.go_to_home)

        layout.addWidget(btn_select)
        layout.addWidget(btn_custom)
        layout.addWidget(btn_back)
        return page

    def create_select_text_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        lbl_info = QLabel("select text to read")
        lbl_info.setStyleSheet(
            "color: #FFD700; font-size: 11px; padding-bottom: 2px;"
        )

        self.btn_read_stop = QPushButton("Read Text")
        btn_back = QPushButton("◀ Back")

        font_metrics = QFontMetrics(page.font())
        btn_width = (
            font_metrics.horizontalAdvance("Read Selected Text") + 25
        )

        self.btn_read_stop.setFixedWidth(btn_width)
        btn_back.setFixedWidth(btn_width)

        self.btn_read_stop.clicked.connect(self.handle_read_selected)
        btn_back.clicked.connect(
            lambda: self.popup_menu.stacked_widget.setCurrentWidget(
                self.popup_menu.page_text_options
            )
        )

        layout.addWidget(lbl_info)
        layout.addWidget(self.btn_read_stop)
        layout.addWidget(btn_back)
        return page

    def create_custom_text_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        expanded_width = 240

        self.custom_input = QTextEdit()
        self.custom_input.setPlaceholderText("Enter custom text here...")
        self.custom_input.setFixedSize(expanded_width, 130)

        self.btn_custom_read = QPushButton("Read Text")
        btn_back = QPushButton("◀ Back")

        self.btn_custom_read.setFixedWidth(expanded_width)
        btn_back.setFixedWidth(expanded_width)

        self.btn_custom_read.clicked.connect(self.handle_read_custom)
        btn_back.clicked.connect(
            lambda: self.popup_menu.stacked_widget.setCurrentWidget(
                self.popup_menu.page_text_options
            )
        )

        layout.addWidget(self.custom_input)
        layout.addWidget(self.btn_custom_read)
        layout.addWidget(btn_back)
        return page

    def create_speech_options_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        expanded_width = 240

        self.speech_output = QTextEdit()
        self.speech_output.setReadOnly(False)
        self.speech_output.setPlaceholderText(
            "Spoken text will appear here clearly..."
        )
        self.speech_output.setFixedSize(expanded_width, 130)

        self.btn_start_speaking = QPushButton("🎙 Start Speaking")
        self.btn_stop_speaking = QPushButton("⏹ Stop Speaking")
        self.btn_clear_text = QPushButton("🧹 Clear Text")
        self.btn_repeat_speaking = QPushButton("🔄 Repeat Speaking")
        self.btn_speech_back = QPushButton("◀ Back")

        for b in (
            self.btn_start_speaking,
            self.btn_stop_speaking,
            self.btn_clear_text,
            self.btn_repeat_speaking,
            self.btn_speech_back,
        ):
            b.setFixedWidth(expanded_width)

        self.btn_stop_speaking.hide()
        self.btn_clear_text.hide()
        self.btn_repeat_speaking.hide()

        self.btn_start_speaking.clicked.connect(self.start_speaking)
        self.btn_stop_speaking.clicked.connect(self.stop_speaking)
        self.btn_clear_text.clicked.connect(self.clear_speech_text)
        self.btn_repeat_speaking.clicked.connect(self.start_speaking)
        self.btn_speech_back.clicked.connect(self.go_to_home)

        layout.addWidget(self.speech_output)
        layout.addWidget(self.btn_start_speaking)
        layout.addWidget(self.btn_stop_speaking)
        layout.addWidget(self.btn_clear_text)
        layout.addWidget(self.btn_repeat_speaking)
        layout.addWidget(self.btn_speech_back)
        return page

    def create_more_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        btn_width = 170

        label = QLabel("Select Voice:")
        label.setStyleSheet("color: #FFD700; font-weight: bold;")
        layout.addWidget(label)

        try:
            temp_engine = pyttsx3.init()
            voices = temp_engine.getProperty("voices")
            for voice in voices:
                btn_v = QPushButton()
                btn_v.setFixedWidth(btn_width)
                btn_v.clicked.connect(
                    lambda checked, v_id=voice.id: self.set_voice(v_id)
                )
                self.voice_buttons[voice.id] = (btn_v, voice.name)
                layout.addWidget(btn_v)
            del temp_engine
            self.update_voice_selection_ui()
        except Exception:
            pass

        btn_back = QPushButton("◀ Back")
        btn_back.setFixedWidth(btn_width)
        btn_back.clicked.connect(self.go_to_home)
        layout.addWidget(btn_back)
        return page

    def update_voice_selection_ui(self):
        for voice_id, (btn, voice_name) in self.voice_buttons.items():
            if voice_id == self.selected_voice_id:
                btn.setText(f"✓ {voice_name}")
                btn.setProperty("selected", "true")
            else:
                btn.setText(f"🔊 {voice_name}")
                btn.setProperty("selected", "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_voice(self, voice_id):
        self.selected_voice_id = voice_id
        self.update_voice_selection_ui()

    def handle_read_selected(self):
        if not self.is_reading:
            try:
                # Hide icon first so focus shifts back to the target app for Ctrl+C
                self.hide_icon()
                QApplication.processEvents()

                pyperclip.copy("")
                send_ctrl_c_safe()
                time.sleep(0.1)

                selected_text = str(pyperclip.paste()).strip()

                if selected_text:
                    # Valid text found -> Stay hidden and start reading
                    self.is_reading = True
                    self.btn_read_stop.setText("Stop Reading")
                    threading.Thread(
                        target=self._run_tts,
                        args=(
                            selected_text,
                            self.btn_read_stop,
                            "Read Text",
                        ),
                        daemon=True,
                    ).start()
                else:
                    # No text selected -> Bring the icon and menu back immediately on Select Text page
                    self.show_icon()
                    if self.popup_menu:
                        self.popup_menu.stacked_widget.setCurrentWidget(
                            self.popup_menu.page_select_text
                        )
                        self.update_popup_position()
                        self.popup_menu.show()

                    self.show_centered_message(
                        QMessageBox.Icon.Information,
                        "Notice",
                        "Please select text to read",
                    )
            except Exception as e:
                self.show_icon()
                if self.popup_menu:
                    self.popup_menu.show()
                self.show_centered_message(
                    QMessageBox.Icon.Warning,
                    "Error",
                    f"Unable to copy selection: {str(e)}",
                )
        else:
            self.is_reading = False
            self.btn_read_stop.setText("Read Text")

    def handle_read_custom(self):
        if not self.is_reading:
            clean_text = self.custom_input.toPlainText().strip()
            if clean_text:
                self.is_reading = True
                self.btn_custom_read.setText("Stop Reading")
                threading.Thread(
                    target=self._run_tts,
                    args=(clean_text, self.btn_custom_read, "Read Text"),
                    daemon=True,
                ).start()
            else:
                self.show_centered_message(
                    QMessageBox.Icon.Information,
                    "Notice",
                    "Please enter text to read",
                )
        else:
            self.is_reading = False
            self.btn_custom_read.setText("Read Text")

    def _run_tts(self, text, button_widget, original_label):
        engine = None
        completed_successfully = False
        try:
            if not text:
                return
            engine = pyttsx3.init()
            engine.setProperty("rate", self.speech_rate)

            if self.selected_voice_id:
                engine.setProperty("voice", self.selected_voice_id)

            engine.say(text)
            engine.runAndWait()
            completed_successfully = True
        except Exception:
            pass
        finally:
            if engine:
                try:
                    engine.stop()
                except Exception:
                    pass
                del engine

            self.is_reading = False
            button_widget.setText(original_label)

            self.show_icon()
            if completed_successfully:
                self.return_home_signal.emit()

    def stop_tts(self, button_widget, original_label):
        self.is_reading = False
        button_widget.setText(original_label)
        self.go_to_home()

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.recorded_chunks.append(indata.copy())

    def start_speaking(self):
        self.is_recording = True
        self.recorded_chunks = []
        self.speech_output.setText("Recording... Speak into your mic now.")

        self.btn_start_speaking.hide()
        self.btn_clear_text.hide()
        self.btn_repeat_speaking.hide()
        self.btn_stop_speaking.show()

        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                callback=self._audio_callback,
            )
            self.stream.start()
        except Exception as e:
            self.speech_output.setText(f"Mic error: {str(e)}")
            self.reset_speech_ui()

    def stop_speaking(self):
        if self.is_recording:
            self.is_recording = False
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass

            self.btn_start_speaking.hide()
            self.btn_stop_speaking.hide()
            self.btn_clear_text.show()
            self.btn_repeat_speaking.show()

            if self.recorded_chunks:
                self.speech_output.setText("Processing spoken audio...")
                audio_data = np.concatenate(self.recorded_chunks, axis=0)

                self.speech_thread = SpeechWorker(
                    audio_data, self.sample_rate
                )
                self.speech_thread.finished_signal.connect(
                    self.on_speech_finished
                )
                self.speech_thread.start()
            else:
                self.speech_output.setText("No audio was recorded.")

    def clear_speech_text(self):
        self.speech_output.clear()

    def reset_speech_ui(self):
        self.btn_stop_speaking.hide()
        self.btn_clear_text.hide()
        self.btn_repeat_speaking.hide()
        self.btn_start_speaking.show()

    def on_speech_finished(self, text):
        self.speech_output.setText(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = FloatingWidget()
    window.show()
    sys.exit(app.exec())