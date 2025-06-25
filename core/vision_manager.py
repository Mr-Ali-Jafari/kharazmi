import cv2
import mediapipe as mp
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QSize
from PyQt5.QtGui import QImage, QPixmap
import time

class VisionThread(QThread):
    frame_ready = pyqtSignal(QImage)
    key_pressed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    size_changed = pyqtSignal(QSize)

    def __init__(self, camera_index):
        super().__init__()
        self.camera_index = camera_index
        self.running = False
        self.cap = None
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.last_key_press_time = 0
        self.key_press_cooldown = 3.0  # 3 seconds hold time
        self.current_key = None
        self.key_start_time = None
        self.key_emitted = False
        self.current_word = ""  # برای ذخیره کلمه در حال نوشتن
        self.last_word_time = 0  # برای تشخیص پایان کلمه
        self.sentence = ""  # برای ذخیره جمله کامل
        self.text_emitted = False  # برای جلوگیری از ارسال مجدد متن

    def create_keyboard_layout(self):
        # کلیدهای اصلی
        keys = [
            ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
            ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
            ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
            ['z', 'x', 'c', 'v', 'b', 'n', 'm'],
            ['(', ')', '"', "'", 'SE', 'ET', 'BC']
        ]
        return keys

    def draw_keyboard(self, frame):
        height, width = frame.shape[:2]
        keys = self.create_keyboard_layout()
        
        # تنظیم اندازه کلیدها (کوچکتر)
        key_height = height // (len(keys) + 4)  # تقسیم بر 4 برای کوچکتر کردن
        key_width = width // 12  # کلیدها را باریک‌تر می‌کنیم

        # نمایش کلمه در حال نوشتن و جمله کامل
        if self.current_word:
            cv2.putText(frame, f"کلمه: {self.current_word}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)  # کاهش سایز فونت
        if self.sentence:
            cv2.putText(frame, f"جمله: {self.sentence}", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)  # کاهش سایز فونت

        # محاسبه موقعیت کیبورد
        keyboard_y = height - (len(keys) * key_height) - 20

        for i, row in enumerate(keys):
            row_width = len(row) * key_width
            start_x = (width - row_width) // 2
            for j, key in enumerate(row):
                x = start_x + j * key_width
                y = keyboard_y + i * key_height
                
                # تنظیم عرض کلیدهای خاص
                if key in ['SE', 'ET', 'BC']:
                    key_width_multiplier = 2  # دو برابر عرض عادی
                else:
                    key_width_multiplier = 1
                
                # تغییر رنگ کلید فعلی
                if self.current_key == key:
                    if self.key_start_time:
                        hold_time = time.time() - self.key_start_time
                        if hold_time >= self.key_press_cooldown:
                            color = (0, 0, 255)  # قرمز برای کلید آماده
                        else:
                            progress = hold_time / self.key_press_cooldown
                            color = (0, int(255 * (1 - progress)), 0)
                    else:
                        color = (0, 255, 0)
                else:
                    color = (0, 255, 0)
                
                # رسم کلید با اندازه تنظیم شده
                cv2.rectangle(frame, (x, y), (x + (key_width * key_width_multiplier) - 5, y + key_height - 5), color, 2)
                # متن کوچکتر
                font_scale = 0.6  # کاهش سایز فونت
                thickness = 1  # کاهش ضخامت فونت
                cv2.putText(frame, key, (x + 10, y + key_height - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)

    def detect_key_press(self, frame, hand_landmarks):
        if not hand_landmarks:
            self.current_key = None
            self.key_start_time = None
            return None

        height, width = frame.shape[:2]
        keys = self.create_keyboard_layout()
        key_height = height // (len(keys) + 4)
        key_width = width // 12

        # Get index finger tip position
        index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
        x = int(index_tip.x * width)
        y = int(index_tip.y * height)

        # Draw finger position with smaller circle
        cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)  # کاهش سایز دایره

        # محاسبه موقعیت کیبورد
        keyboard_y = height - (len(keys) * key_height) - 20

        # Check which key is being pressed
        current_key = None
        for i, row in enumerate(keys):
            row_width = len(row) * key_width
            start_x = (width - row_width) // 2
            for j, key in enumerate(row):
                key_x = start_x + j * key_width
                key_y = keyboard_y + i * key_height
                if (key_x < x < key_x + key_width - 5 and 
                    key_y < y < key_y + key_height - 5):
                    current_key = key
                    break
            if current_key:
                break

        # Handle key press timing
        if current_key:
            if self.current_key == current_key:
                if not self.key_start_time:
                    self.key_start_time = time.time()
                elif time.time() - self.key_start_time >= self.key_press_cooldown and not self.key_emitted:
                    self.key_emitted = True
                    return current_key
            else:
                self.current_key = current_key
                self.key_start_time = time.time()
                self.key_emitted = False
        else:
            self.current_key = None
            self.key_start_time = None
            self.key_emitted = False

        return None

    def run(self):
        try:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_ANY)
            
            if not self.cap.isOpened():
                self.error_occurred.emit("خطا در باز کردن دوربین. لطفاً مطمئن شوید که دوربین به درستی متصل است.")
                return

            # تنظیم پارامترهای دوربین
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)  # افزایش رزولوشن
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cap.set(cv2.CAP_PROP_FPS, 30)

            self.running = True
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    self.error_occurred.emit("خطا در خواندن فریم از دوربین")
                    break

                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.hands.process(rgb_frame)
                
                self.draw_keyboard(frame)
                
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                        key = self.detect_key_press(frame, hand_landmarks)
                        if key:
                            if key == 'SE':  # Space
                                if self.current_word and not self.text_emitted:
                                    self.sentence += self.current_word
                                    self.key_pressed.emit(self.current_word)
                                    self.current_word = ""
                                    self.key_pressed.emit(" ")
                                    self.text_emitted = True
                            elif key == 'ET':  # Enter
                                if self.current_word and not self.text_emitted:
                                    self.sentence += self.current_word
                                    self.key_pressed.emit(self.current_word)
                                    self.current_word = ""
                                self.key_pressed.emit('\n')
                                self.sentence = ""  # پاک کردن جمله برای شروع جمله جدید
                                self.text_emitted = True
                            elif key == 'BC':  # Backspace
                                if self.current_word:
                                    self.current_word = self.current_word[:-1]
                                    self.key_pressed.emit('backspace')
                                elif self.sentence:
                                    # حذف آخرین کلمه از جمله
                                    words = self.sentence.split()
                                    if words:
                                        words.pop()
                                        self.sentence = " ".join(words)
                                        self.key_pressed.emit(self.sentence)
                                self.text_emitted = True
                            else:
                                self.current_word += key
                                self.last_word_time = time.time()
                                self.text_emitted = False

                # اگر 2 ثانیه از آخرین حرف گذشته باشد، کلمه را به جمله اضافه کن
                if self.current_word and time.time() - self.last_word_time > 2 and not self.text_emitted:
                    self.sentence += self.current_word
                    self.key_pressed.emit(self.current_word)
                    self.current_word = ""
                    self.text_emitted = True

                height, width = frame.shape[:2]
                bytes_per_line = 3 * width
                q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
                self.frame_ready.emit(q_image)

        except Exception as e:
            self.error_occurred.emit(f"خطا در اجرای دوربین: {str(e)}")
        finally:
            if self.cap:
                self.cap.release()
            self.hands.close()

    def stop(self):
        self.running = False

class VisionManager:
    def __init__(self):
        self.available_cameras = self._get_available_cameras()
        self.vision_thread = None

    def _get_available_cameras(self):
        available = []
        # بررسی دوربین‌های موجود
        for i in range(4):  # Check first 4 camera indices
            try:
                cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
                if not cap.isOpened():
                    cap = cv2.VideoCapture(i, cv2.CAP_ANY)
                
                if cap.isOpened():
                    available.append(i)
                    cap.release()
                    break  # فقط اولین دوربین موجود را برگردان
            except:
                continue
        return available

    def start_vision(self, camera_index):
        if self.vision_thread and self.vision_thread.isRunning():
            self.stop_vision()
        
        self.vision_thread = VisionThread(camera_index)
        self.vision_thread.start()
        return True

    def stop_vision(self):
        if self.vision_thread:
            self.vision_thread.stop()
            self.vision_thread.wait()
            self.vision_thread = None