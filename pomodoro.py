import sys
import os
import struct
import math
import tempfile
import threading

# 引入 pygame 处理音频
import pygame

from PySide6.QtWidgets import (QApplication, QWidget, QSystemTrayIcon, QMenu,
                               QInputDialog, QDialog, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout, QFontDialog, QGraphicsDropShadowEffect, QFileDialog, QMessageBox)
from PySide6.QtCore import (QTimer, Qt, QTime, QPoint, QRectF, QUrl,
                            QPropertyAnimation, QEasingCurve, QPointF, QSettings, QSize, QRect)
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QImage,
                           QAction, QPainterPath, QLinearGradient, QCursor, QPixmap, QBitmap)


# --- 🎵 音频管理器 ---
class AudioManager:
    def __init__(self):
        try:
            pygame.mixer.init()
            self.is_ready = True
        except Exception as e:
            print(f"Pygame init failed: {e}")
            self.is_ready = False
        self.builtin_alarm = self._create_builtin_wav()

    def _create_builtin_wav(self):
        try:
            duration_sec = 2
            sample_rate = 44100
            n_samples = int(sample_rate * duration_sec)
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            header = struct.pack('<4sI4s', b'RIFF', 36 + n_samples * 2, b'WAVE')
            fmt = struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
            data_header = struct.pack('<4sI', b'data', n_samples * 2)
            with open(temp_file.name, 'wb') as f:
                f.write(header);
                f.write(fmt);
                f.write(data_header)
                freq = 880
                volume = 20000
                for i in range(n_samples):
                    t = i / sample_rate
                    if (t % 0.5) < 0.1:
                        sample = volume * math.sin(2 * math.pi * freq * t)
                    else:
                        sample = 0
                    f.write(struct.pack('<h', int(sample)))
            return temp_file.name
        except:
            return None

    def play(self, file_path=None):
        if not self.is_ready: return
        try:
            pygame.mixer.music.stop()
            if file_path and os.path.exists(file_path):
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play(-1)
                return
            if self.builtin_alarm:
                pygame.mixer.music.load(self.builtin_alarm)
                pygame.mixer.music.play(-1)
        except Exception as e:
            print(f"Play Error: {e}")

    def stop(self):
        if self.is_ready: pygame.mixer.music.stop()


# --- 🛠️ 主题弹窗 ---
class ThemeDialog(QDialog):
    def __init__(self, title, message, theme_data, parent=None):
        super().__init__(parent)
        self.theme = theme_data
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        accent_color = self.theme["colors"][0].name()
        text_color = "#333333"

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            f"font-family: 'Microsoft YaHei'; font-size: 24px; font-weight: bold; color: {text_color}; background: transparent;")

        self.msg_label = QLabel(message)
        self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg_label.setWordWrap(True)
        self.msg_label.setStyleSheet(
            f"font-family: 'Microsoft YaHei'; font-size: 18px; color: {text_color}; background: transparent;")

        self.btn = QPushButton("我知道了")
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setFixedSize(140, 45)

        self.btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent_color}; color: #ffffff; border: none; border-radius: 22px;
                font-family: 'Microsoft YaHei'; font-size: 16px; font-weight: bold;
            }}
            QPushButton:hover {{ opacity: 0.8; }}
        """)
        self.btn.clicked.connect(self.accept)

        layout.addWidget(self.title_label)
        layout.addWidget(self.msg_label)
        layout.addStretch()
        layout.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)
        self.setMinimumWidth(360)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_color = QColor("#FFFAFA")

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 20, 20)

        painter.setPen(QPen(self.theme["colors"][0], 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 20, 20)


class UltimatePomodoro(QWidget):
    def __init__(self):
        super().__init__()

        self.settings = QSettings("MyCompany", "PomodoroProV19")

        # --- 核心数据 ---
        self.work_duration = int(self.settings.value("work_duration", 25))
        self.break_duration = int(self.settings.value("break_duration", 5))
        self.target_cycles = int(self.settings.value("target_cycles", 4))
        self.current_theme = self.settings.value("theme", "Doro")
        self.custom_font_family = self.settings.value("font_family", "Segoe UI")
        self.custom_mp3_path = self.settings.value("custom_mp3_path", "")

        self.audio_mgr = AudioManager()

        self.total_time = self.work_duration * 60
        self.current_time = self.total_time
        self.is_running = False
        self.mode = "WORK"
        self.current_cycle = 1

        # 窗口尺寸 (适当加大以容纳大图)
        self.window_size = 260
        self.capsule_w = 160
        self.capsule_h = 50

        self.normal_opacity = 0.95
        self.is_hovering_btn = False
        self.dock_pos = None
        self.drag_pos = None

        # --- 🎨 主题库 ---
        self.themes = {
            "Doro": {
                "colors": (QColor(255, 182, 193), QColor(147, 112, 219)),
                "bg": QColor(255, 240, 245),
                "char_img": "doro.png",
                "text": QColor(0, 0, 0)
            },
            "Bubblegum Pop": {
                "colors": (QColor(255, 105, 180), QColor(0, 255, 255)),
                "bg": QColor(255, 240, 245),
                "text": QColor(50, 50, 50)
            },
            "Lemon Meringue": {
                "colors": (QColor(255, 215, 0), QColor(255, 250, 205)),
                "bg": QColor(255, 255, 224),
                "text": QColor(100, 80, 0)
            },
            "Mint Chocolate": {
                "colors": (QColor(152, 255, 152), QColor(0, 250, 154)),
                "bg": QColor(240, 255, 245),
                "text": QColor(0, 100, 80)
            },
            "Lavender Haze": {
                "colors": (QColor(230, 230, 250), QColor(147, 112, 219)),
                "bg": QColor(248, 248, 255),
                "text": QColor(75, 0, 130)
            },
            "Sky Blue Dream": {
                "colors": (QColor(135, 206, 235), QColor(224, 255, 255)),
                "bg": QColor(240, 255, 255),
                "text": QColor(0, 50, 100)
            },
            "Cyberpunk": {
                "colors": (QColor(0, 255, 200), QColor(0, 100, 255)),
                "bg": QColor(20, 20, 30),
                "text": QColor(255, 255, 255)
            },
            "Peach Oolong": {
                "colors": (QColor(255, 182, 193), QColor(255, 127, 80)),
                "bg": QColor(255, 245, 238),
                "text": QColor(70, 70, 70)
            }
        }

        self.char_pixmap = None
        self.load_theme_image()

        self.init_ui()
        self.init_tray()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick_timer)
        self.timer.start(1000)

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.update)
        self.ui_timer.start(30)

        self.dock_timer = QTimer(self)
        self.dock_timer.timeout.connect(self.check_docking)
        self.dock_timer.start(50)

        self._pos_anim = None

    def load_theme_image(self):
        theme = self.themes.get(self.current_theme, self.themes["Doro"])
        img_name = theme.get("char_img")

        if img_name and os.path.exists(img_name):
            self.char_pixmap = QPixmap(img_name)
        else:
            self.char_pixmap = None

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.window_size, self.window_size)
        self.center_on_screen()
        self.setWindowOpacity(self.normal_opacity)

    def center_on_screen(self):
        screen = self.screen().geometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        theme = self.themes.get(self.current_theme, self.themes["Doro"])
        colors = theme["colors"]
        is_urgent = (self.current_time <= 5 and self.is_running)

        if self.dock_pos is None:
            self.draw_orb_mode(painter, theme, colors, is_urgent)
        else:
            self.draw_docked_mode(painter, theme, colors, is_urgent)

    def draw_orb_mode(self, painter, theme, colors, is_urgent):
        margin = 10
        draw_rect = self.rect().adjusted(margin, margin, -margin, -margin)
        radius = draw_rect.width() / 2
        center = draw_rect.center()

        # --- 1. 背景 ---
        bg = theme.get("bg")
        painter.setBrush(QBrush(bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius, radius)

        # --- 2. 轨道 ---
        track_color = QColor(colors[0])
        track_color.setAlpha(60)
        painter.setPen(QPen(track_color, 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawEllipse(center, radius - 5, radius - 5)

        # --- 3. 进度条 ---
        if self.total_time > 0:
            progress = self.current_time / self.total_time
            start_angle = 90 * 16
            span_angle = int(-progress * 360 * 16)

            grad = QLinearGradient(0, 0, self.window_size, self.window_size)
            if is_urgent:
                grad.setColorAt(0, QColor(255, 80, 80))
                grad.setColorAt(1, QColor(255, 0, 0))
            else:
                grad.setColorAt(0, colors[0])
                grad.setColorAt(1, colors[1])

            painter.setPen(QPen(QBrush(grad), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            r_ring = radius - 5
            painter.drawArc(QRectF(center.x() - r_ring, center.y() - r_ring, r_ring * 2, r_ring * 2), start_angle,
                            span_angle)

        # --- 4. 文字 ---
        if is_urgent:
            main_text_color = QColor(255, 0, 0)
        else:
            main_text_color = theme.get("text", QColor(255, 255, 255))

        painter.setPen(main_text_color)
        painter.setFont(QFont(self.custom_font_family, 38, QFont.Weight.Bold))
        mins, secs = divmod(self.current_time, 60)
        time_str = f"{mins:02d}:{secs:02d}"

        fm = painter.fontMetrics()
        w = fm.horizontalAdvance(time_str)
        painter.drawText(QPointF(center.x() - w / 2, center.y() + 5), time_str)

        # --- 5. 系统时间 ---
        painter.setFont(QFont("Segoe UI", 9))
        sys_color = QColor(main_text_color)
        sys_color.setAlpha(200)
        painter.setPen(sys_color)
        painter.drawText(QRectF(0, 35, self.window_size, 20), Qt.AlignmentFlag.AlignCenter,
                         QTime.currentTime().toString("HH:mm"))

        # --- 6. 按钮 ---
        self.draw_button(painter, center, main_text_color)

        # --- 7. 休息状态 ---
        if self.mode == "BREAK":
            painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
            painter.setPen(colors[1])
            painter.drawText(QRectF(0, self.window_size - 50, self.window_size, 30), Qt.AlignmentFlag.AlignCenter,
                             "💤 休息中~")

    def draw_docked_mode(self, painter, theme, colors, is_urgent):
        # 1. 绘制胶囊 (底部)
        capsule_rect = QRectF(0, 0, self.capsule_w, self.capsule_h)

        if self.dock_pos == 'left':
            capsule_rect.moveBottom(self.window_size - 10)
            capsule_rect.moveLeft(0)
        elif self.dock_pos == 'right':
            capsule_rect.moveBottom(self.window_size - 10)
            capsule_rect.moveRight(self.window_size)
        elif self.dock_pos == 'top':
            capsule_rect.moveTop(0)
            capsule_rect.moveLeft((self.window_size - self.capsule_w) / 2)

        # --- 2. 绘制 Doro (位于胶囊上方，宽度对齐胶囊) ---
        if self.char_pixmap and not self.char_pixmap.isNull():
            # 核心修改：让图片的目标宽度 == 胶囊宽度 (160px)
            # 这样就能充分利用宽度，不会小
            target_w = 180

            # 使用 scaledToWidth 按比例缩放，SmoothTransformation 保证高清
            scaled_doro = self.char_pixmap.scaledToWidth(
                int(target_w),
                Qt.TransformationMode.SmoothTransformation
            )

            # 计算绘制位置：居中对齐胶囊，脚底踩在胶囊上边缘
            draw_x = capsule_rect.left() + (capsule_rect.width() - scaled_doro.width()) / 2
            # Y轴：脚底(draw_y + height) = 胶囊顶部(capsule_rect.top())
            # +10 偏移量让它稍微踩进去一点点，看起来更稳
            draw_y = capsule_rect.top() - scaled_doro.height() + 7

            if self.dock_pos == 'top':
                # 顶部吸附特殊处理：挂在胶囊下面
                draw_y = capsule_rect.bottom() - 18

            # 使用 int 强制像素对齐，防止模糊
            painter.drawPixmap(int(draw_x), int(draw_y), scaled_doro)

        # --- 3. 绘制胶囊本体 ---
        bg = theme.get("bg")
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(capsule_rect, 25, 25)

        border_color = QColor(255, 0, 0) if is_urgent else colors[0]
        painter.setPen(QPen(border_color, 3 if is_urgent else 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(capsule_rect, 25, 25)

        if is_urgent:
            text_color = QColor(255, 0, 0)
        else:
            text_color = theme.get("text")

        painter.setPen(text_color)
        painter.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        mins, secs = divmod(self.current_time, 60)
        painter.drawText(capsule_rect.adjusted(0, -2, 0, 0), Qt.AlignmentFlag.AlignCenter, f"{mins:02d}:{secs:02d}")

    def draw_button(self, painter, center, color):
        btn_y = center.y() + 45
        display_color = color
        if not self.is_hovering_btn:
            alpha = 150
            display_color = QColor(color.red(), color.green(), color.blue(), alpha)
        painter.setBrush(display_color)
        painter.setPen(Qt.PenStyle.NoPen)

        if self.is_running:
            w, h = 6, 18
            painter.drawRoundedRect(center.x() - 8, btn_y - h / 2, w, h, 2, 2)
            painter.drawRoundedRect(center.x() + 2, btn_y - h / 2, w, h, 2, 2)
        else:
            path = QPainterPath()
            x = center.x() - 4
            y = btn_y
            h = 16
            path.moveTo(x, y - h / 2)
            path.lineTo(x + 12, y)
            path.lineTo(x, y + h / 2)
            path.closeSubpath()
            painter.drawPath(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            center_y = self.height() / 2
            click_y = event.position().y()
            if self.dock_pos is None and click_y > center_y + 30 and click_y < self.height() - 40:
                self.toggle_timer()
            else:
                self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        pos = event.position()
        center_y = self.height() / 2
        is_on_btn = (pos.y() > center_y + 30 and pos.y() < self.height() - 40) and not self.dock_pos
        if is_on_btn != self.is_hovering_btn:
            self.is_hovering_btn = is_on_btn
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos:
            if self.dock_pos:
                self.dock_pos = None
                self.update()
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def check_docking(self):
        if QApplication.mouseButtons() == Qt.MouseButton.LeftButton: return
        geo = self.geometry()
        screen_geo = self.screen().geometry()
        snap_margin = 20
        new_dock_pos = self.dock_pos

        if not self.dock_pos:
            if geo.top() < snap_margin:
                new_dock_pos = 'top'
            elif geo.left() < snap_margin:
                new_dock_pos = 'left'
            elif geo.right() > screen_geo.width() - snap_margin:
                new_dock_pos = 'right'

        if new_dock_pos:
            self.dock_pos = new_dock_pos
            target_pos = geo.topLeft()

            if self.dock_pos == 'top':
                target_pos = QPoint(geo.x(), 0)
            elif self.dock_pos == 'left':
                target_pos = QPoint(0, geo.y())
            elif self.dock_pos == 'right':
                target_pos = QPoint(screen_geo.width() - self.window_size, geo.y())

            if geo.topLeft() != target_pos:
                self._pos_anim = QPropertyAnimation(self, b"pos")
                self._pos_anim.setDuration(300)
                self._pos_anim.setStartValue(self.pos())
                self._pos_anim.setEndValue(target_pos)
                self._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                self._pos_anim.start()

            pull_dist = 50
            if self.dock_pos == 'top' and geo.y() > pull_dist: self.dock_pos = None
            if self.dock_pos == 'left' and geo.x() > pull_dist: self.dock_pos = None
            if self.dock_pos == 'right' and geo.x() < screen_geo.width() - self.window_size - pull_dist: self.dock_pos = None

    def tick_timer(self):
        if self.is_running:
            self.current_time -= 1
            if self.current_time <= 0:
                self.finish_cycle()

    def toggle_timer(self):
        self.is_running = not self.is_running

    def finish_cycle(self):
        self.is_running = False
        self.update()
        self.audio_mgr.play(self.custom_mp3_path)

        title, msg = "", ""
        if self.mode == "WORK":
            title = "专注结束"
            msg = f"当前是第 {self.current_cycle} / {self.target_cycles} 轮专注！\n现在放松一下喝口水吧~ 🥤"
            self.mode = "BREAK"
            self.total_time = self.break_duration * 60
            self.current_time = self.total_time
            self.is_running = True
        else:
            if self.current_cycle >= self.target_cycles:
                title = "恭喜！🎉"
                msg = "真棒！你在成为更好的自己！\n今日专注计划已完成。"
                self.current_cycle = 1
                self.mode = "WORK"
                self.total_time = self.work_duration * 60
                self.current_time = self.total_time
                self.is_running = False
            else:
                title = "准备开始"
                msg = "休息结束，电量充满！\n准备进入下一轮专注。💪"
                self.current_cycle += 1
                self.mode = "WORK"
                self.total_time = self.work_duration * 60
                self.current_time = self.total_time
                self.is_running = True

        theme = self.themes.get(self.current_theme, self.themes["Doro"])
        dlg = ThemeDialog(title, msg, theme, self)
        screen = self.screen().geometry()
        dlg.move((screen.width() - dlg.width()) // 2, (screen.height() - dlg.height()) // 2)
        dlg.exec()
        self.audio_mgr.stop()

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { font-size: 14px; padding: 5px; }")

        info_action = QAction(f"📊 进度: 第 {self.current_cycle}/{self.target_cycles} 轮", self)
        info_action.setEnabled(False)
        menu.addAction(info_action)
        menu.addSeparator()

        menu.addAction("🔠 设置字体...", self.choose_font)

        theme_menu = menu.addMenu("🎨 切换主题")
        for name in self.themes:
            action = QAction(name, self)
            action.triggered.connect(lambda checked, n=name: self.set_theme(n))
            theme_menu.addAction(action)

        mp3_name = "默认内置"
        if self.custom_mp3_path and os.path.exists(self.custom_mp3_path):
            mp3_name = os.path.basename(self.custom_mp3_path)
            if len(mp3_name) > 15: mp3_name = mp3_name[:12] + "..."

        audio_action = QAction(f"🎵 选择 MP3 铃声... (当前:{mp3_name})", self)
        audio_action.triggered.connect(self.choose_mp3)
        menu.addAction(audio_action)

        menu.addSeparator()
        menu.addAction("设置目标轮数...", self.set_total_cycles)
        menu.addAction("设置专注时长...", self.set_work_time)
        menu.addAction("设置休息时长...", self.set_break_time)
        menu.addSeparator()

        reset_action = QAction("重置当前计时", self)
        reset_action.triggered.connect(self.reset_timer)
        menu.addAction(reset_action)
        menu.addAction("退出", QApplication.instance().quit)
        menu.exec(pos)

    def choose_mp3(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择铃声", "", "Audio Files (*.mp3 *.wav *.ogg *.flac)")
        if file_path:
            self.custom_mp3_path = file_path
            self.settings.setValue("custom_mp3_path", file_path)
            QMessageBox.information(self, "成功", "铃声设置成功！")

    def choose_font(self):
        current = QFont(self.custom_font_family)
        ok, font = QFontDialog.getFont(current, self, "选择时间显示字体")
        if ok:
            self.custom_font_family = font.family()
            self.settings.setValue("font_family", self.custom_font_family)

    def set_theme(self, name):
        self.current_theme = name
        self.settings.setValue("theme", name)
        self.load_theme_image()
        self.update()

    def set_work_time(self):
        t, ok = QInputDialog.getInt(self, "设置", "专注分钟:", self.work_duration, 1, 120)
        if ok:
            self.work_duration = t
            self.settings.setValue("work_duration", t)
            if self.mode == "WORK": self.reset_timer()

    def set_break_time(self):
        t, ok = QInputDialog.getInt(self, "设置", "休息分钟:", self.break_duration, 1, 60)
        if ok:
            self.break_duration = t
            self.settings.setValue("break_duration", t)
            if self.mode == "BREAK": self.reset_timer()

    def set_total_cycles(self):
        c, ok = QInputDialog.getInt(self, "设置", "总轮数:", self.target_cycles, 1, 20)
        if ok:
            self.target_cycles = c
            self.settings.setValue("target_cycles", c)
            self.current_cycle = 1

    def reset_timer(self):
        self.is_running = False
        duration = self.work_duration if self.mode == "WORK" else self.break_duration
        self.total_time = duration * 60
        self.current_time = self.total_time
        self.update()

    def init_tray(self):
        self.tray = QSystemTrayIcon(self)
        pixmap = QApplication.style().standardPixmap(QApplication.style().StandardPixmap.SP_ComputerIcon)
        self.tray.setIcon(pixmap)
        menu = QMenu()
        menu.addAction("显示/隐藏", lambda: self.setVisible(not self.isVisible()))
        menu.addAction("退出", QApplication.instance().quit)
        self.tray.setContextMenu(menu)
        self.tray.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    clock = UltimatePomodoro()
    clock.show()
    sys.exit(app.exec())