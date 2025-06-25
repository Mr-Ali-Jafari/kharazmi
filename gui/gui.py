import subprocess
import logging
import traceback
import sys
import os
import time
import io
from typing import Optional, List, Tuple, Any
from contextlib import contextmanager

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QPushButton, 
    QVBoxLayout, QWidget, QLabel, QTextEdit, QLineEdit, QTabWidget, 
    QListWidget, QInputDialog, QComboBox, QHBoxLayout, QShortcut,
    QProgressBar, QStatusBar, QGroupBox, QCheckBox, QSpinBox,
    QScrollArea
)
from PyQt5.QtGui import (
    QColor, QTextCharFormat, QSyntaxHighlighter, QTextOption, 
    QPixmap, QKeySequence, QFont, QIcon
)
from PyQt5.QtCore import (
    Qt, QTimer, QDateTime, QUrl, QThread, pyqtSignal, 
    QLibraryInfo, QObject, QMutex, QWaitCondition
)
from PyQt5.QtWebSockets import QWebSocket

import git
import webbrowser

# Import core modules with error handling
try:
    from core.framework_detector import detect_framework
    from core.import_manager import convert_imports_to_relative
    from core.project_organizer import create_structure, categorize_files
    from core.ai_manager import AIManager
    from core.vision_manager import VisionManager
    from gui.settings_manager import SettingsManager
except ImportError as e:
    print(f"Warning: Could not import core modules: {e}")
    # Create dummy functions to prevent crashes
    def detect_framework(path): return "Unknown"
    def convert_imports_to_relative(path): pass
    def create_structure(path, framework): pass
    def categorize_files(path): pass
    class AIManager:
        def __init__(self, api_key): pass
        def get_ai_response(self, prompt): return "AI service unavailable"
    class VisionManager:
        def __init__(self): 
            self.available_cameras = []
            self.vision_thread = None
        def start_vision(self, camera_index): return False
        def stop_vision(self): pass
    class SettingsManager:
        def __init__(self): pass
        def get_ai_api_key(self, provider): return ""
        def set_ai_api_key(self, provider, api_key): return True
        def get_websocket_config(self): return {}
        def set_websocket_config(self, config): return True
        def get_setting(self, category, key, default=None): return default
        def set_setting(self, category, key, value): return True
        def reset_to_defaults(self): return True
        def get_all_settings(self): return {}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('codeprime.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global error handler
def global_exception_handler(exctype, value, traceback_obj):
    """Global exception handler to prevent crashes"""
    error_msg = f"Unhandled exception: {exctype.__name__}: {value}"
    logger.error(error_msg, exc_info=(exctype, value, traceback_obj))
    
    # Show user-friendly error message
    try:
        app = QApplication.instance()
        if app:
            QMessageBox.critical(None, "خطا", f"خطای غیرمنتظره رخ داد:\n{str(value)}\n\nلطفاً برنامه را مجدداً راه‌اندازی کنید.")
    except:
        pass

sys.excepthook = global_exception_handler

@contextmanager
def safe_operation(operation_name: str, default_return: Any = None):
    """Context manager for safe operations with error handling"""
    try:
        yield
    except Exception as e:
        logger.error(f"Error in {operation_name}: {e}", exc_info=True)
        if default_return is not None:
            return default_return

def setup_persian_fonts(app: QApplication) -> str:
    """
    Set up Persian fonts for the application with proper fallbacks and error handling
    """
    try:
        # Persian font families in order of preference
        persian_fonts = [
            'Vazirmatn',           # Modern Persian font
            'B Nazanin',           # Traditional Persian font
            'B Titr',              # Persian display font
            'B Yekan',             # Modern Persian font
            'B Mitra',             # Persian font
            'B Lotus',             # Persian font
            'B Traffic',           # Persian font
            'Tahoma',              # Windows Persian support
            'Arial Unicode MS',    # Unicode support
            'Segoe UI',            # Windows UI font with Persian support
            'sans-serif'           # Fallback
        ]
        
        # Create font family string
        font_family = ', '.join(persian_fonts)
        
        # Set application font
        app_font = QFont()
        app_font.setFamily(persian_fonts[0])  # Use Vazirmatn as primary
        app_font.setPointSize(10)
        app.setFont(app_font)
        
        logger.info("Persian fonts configured successfully")
        return font_family
        
    except Exception as e:
        logger.error(f"Error setting up Persian fonts: {e}")
        return "'Tahoma', 'Arial Unicode MS', sans-serif"  # Fallback


class SafeFileManager:
    """Thread-safe file manager with error handling"""
    
    def __init__(self):
        self.project_path: Optional[str] = None
        self.mutex = QMutex()
        self._cache = {}
        self._cache_timestamp = 0
        self._cache_timeout = 300  # 5 minutes

    def get_all_files(self, project_path: str) -> List[str]:
        """Get all files in project with caching and error handling"""
        try:
            self.mutex.lock()
            
            # Check cache
            current_time = time.time()
            if (project_path in self._cache and 
                current_time - self._cache_timestamp < self._cache_timeout):
                return self._cache[project_path]
            
            files = []
            if os.path.exists(project_path):
                for root, dirs, files_in_dir in os.walk(project_path):
                    # Skip hidden directories and system files
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
                    
                    for file in files_in_dir:
                        if not file.startswith('.'):
                            files.append(os.path.join(root, file))
            
            # Update cache
            self._cache[project_path] = files
            self._cache_timestamp = current_time
            
            logger.info(f"Found {len(files)} files in {project_path}")
            return files

        except Exception as e:
            logger.error(f"Error getting files from {project_path}: {e}")
            return []
        finally:
            self.mutex.unlock()

    def clear_cache(self):
        """Clear the file cache"""
        try:
            self.mutex.lock()
            self._cache.clear()
            self._cache_timestamp = 0
        finally:
            self.mutex.unlock()


class SafeCollaborationClient(QObject):
    """Thread-safe collaboration client with error handling"""
    
    def __init__(self, code_editor):
        super().__init__()
        self.code_editor = code_editor
        self.socket = QWebSocket()
        self.socket.connected.connect(self.on_connected)
        self.socket.textMessageReceived.connect(self.on_message_received)
        self.socket.error.connect(self.on_error)
        self.socket.disconnected.connect(self.on_disconnected)
        self.is_receiving = False  
        self.connection_retry_count = 0
        self.max_retries = 3
        self.retry_timer = QTimer()
        self.retry_timer.timeout.connect(self.retry_connection)
        self.connected = False

    def connect(self, url: str):
        """Connect to collaboration server with retry logic"""
        try:
            self.socket.open(QUrl(url))
            logger.info(f"Attempting to connect to {url}")
        except Exception as e:
            logger.error(f"Error connecting to {url}: {e}")

    def on_connected(self):
        """Handle successful connection"""
        try:
            self.connected = True
            self.connection_retry_count = 0
            logger.info("Connected to collaboration server")
        except Exception as e:
            logger.error(f"Error in on_connected: {e}")

    def on_message_received(self, message: str):
        """Handle received message with error handling"""
        try:
            logger.debug(f"Received message: {message[:100]}...")
            self.is_receiving = True 
            if hasattr(self.code_editor, 'setPlainText'):
                self.code_editor.setPlainText(message)
            self.is_receiving = False  
        except Exception as e:
            logger.error(f"Error processing received message: {e}")
            self.is_receiving = False  

    def on_error(self, error):
        """Handle connection errors with retry logic"""
        try:
            logger.error(f"WebSocket error: {error}")
            self.connected = False
            
            if self.connection_retry_count < self.max_retries:
                self.connection_retry_count += 1
                self.retry_timer.start(5000)  # Retry after 5 seconds
            else:
                logger.error("Max retry attempts reached")
        except Exception as e:
            logger.error(f"Error in on_error: {e}")

    def on_disconnected(self):
        """Handle disconnection"""
        try:
            self.connected = False
            logger.info("Disconnected from collaboration server")
        except Exception as e:
            logger.error(f"Error in on_disconnected: {e}")

    def retry_connection(self):
        """Retry connection to server"""
        try:
            if not self.connected and self.connection_retry_count < self.max_retries:
                logger.info(f"Retrying connection (attempt {self.connection_retry_count + 1})")
                self.socket.open(QUrl("ws://81.161.229.152:8765"))
        except Exception as e:
            logger.error(f"Error in retry_connection: {e}")

    def send_message(self, message: str):
        """Send message with error handling"""
        try:
            if not self.is_receiving and self.connected:
                self.socket.sendTextMessage(message)
                logger.debug(f"Sent message: {message[:100]}...")
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    def close(self):
        """Safely close the connection"""
        try:
            self.retry_timer.stop()
            if self.socket.state() == QWebSocket.ConnectedState:
                self.socket.close()
        except Exception as e:
            logger.error(f"Error closing connection: {e}")


class SafePythonSyntaxHighlighter(QSyntaxHighlighter):
    """Thread-safe syntax highlighter with error handling"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keywords = [
            "def", "class", "import", "from", "return", "if", "else", "elif", 
            "for", "while", "try", "except", "lambda", "with", "as", "in", 
            "is", "not", "and", "or", "True", "False", "None", "self"
        ]
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("blue"))
        self.keyword_format.setFontWeight(QFont.Bold)
        
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("green"))
        
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("red"))

    def highlightBlock(self, text: str):
        """Highlight syntax with error handling"""
        try:
            # Highlight keywords
            for keyword in self.keywords:
                start = 0
                while True:
                    start = text.find(keyword, start)
                    if start == -1:
                        break
                    
                    # Check if it's a word boundary
                    end = start + len(keyword)
                    if ((start == 0 or not text[start-1].isalnum()) and 
                        (end >= len(text) or not text[end].isalnum())):
                        self.setFormat(start, len(keyword), self.keyword_format)
                    start = end

            # Highlight comments
            comment_start = text.find("#")
            if comment_start != -1:
                self.setFormat(comment_start, len(text) - comment_start, self.comment_format)

            # Highlight strings (simple implementation)
            for quote in ['"', "'"]:
                start = 0
                while True:
                    start = text.find(quote, start)
                    if start == -1:
                        break
                    end = text.find(quote, start + 1)
                    if end == -1:
                        break
                    self.setFormat(start, end - start + 1, self.string_format)
                    start = end + 1
                    
        except Exception as e:
            logger.error(f"Error in syntax highlighting: {e}")


class SafeAutoCompleteThread(QThread):
    """Thread-safe auto-complete with error handling"""
    
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, ai_manager, current_text: str):
        super().__init__()
        self.ai_manager = ai_manager
        self.current_text = current_text
        self._running = True

    def run(self):
        """Run auto-complete with error handling"""
        try:
            if not self._running:
                return
                
            prompt = f"Return only the code without any explanations, comments, or additional text:\n\n{self.current_text}"
            response = self.ai_manager.get_ai_response(prompt)
            
            if self._running:
                self.finished.emit(response)

        except Exception as e:
            logger.error(f"Error in auto-complete: {e}")
            if self._running:
                self.error_occurred.emit(f"خطا در دریافت پاسخ از AI: {str(e)}")

    def stop(self):
        """Stop the thread safely"""
        self._running = False
        self.wait()


class SafeCodeEditor(QTextEdit):
    """Thread-safe code editor with comprehensive error handling"""
    
    def __init__(self, ai_manager):
        super().__init__()
        self.setPlaceholderText("$: ...")
        self.setStyleSheet("""
            background-color: #f9f9f9; 
            border: 1px solid #ccc; 
            font-size: 14px;
            font-family: 'Vazirmatn', 'B Nazanin', 'B Yekan', 'Tahoma', 'Arial Unicode MS', 'Segoe UI', sans-serif;
        """)
        self.setWordWrapMode(QTextOption.NoWrap)
        self.highlighter = SafePythonSyntaxHighlighter(self.document())

        self.ai_manager = ai_manager  
        self.timer = QTimer(self) 
        self.timer.setSingleShot(True) 
        self.timer.timeout.connect(self.auto_complete)
        self.last_text = ""
        self.text_was_changed = False
        self.message_box = None
        self.auto_complete_thread = None
        self.auto_complete_enabled = True
        self.max_text_length = 10000  # Prevent excessive text processing

    def set_syntax_highlighting(self, language: str = "Python"):
        """Set syntax highlighting with error handling"""
        try:
            if language == "Python":
                self.highlighter = SafePythonSyntaxHighlighter(self.document())
            elif language == "JavaScript":
                # Add JavaScript highlighting if needed
                pass
        except Exception as e:
            logger.error(f"Error setting syntax highlighting: {e}")

    def keyPressEvent(self, event):
        """Handle key press with error handling"""
        try:
            if event.key() == Qt.Key_Tab:
                self.text_was_changed = True
                self.timer.start(300)  
            else:
                super().keyPressEvent(event)
        except Exception as e:
            logger.error(f"Error in keyPressEvent: {e}")
            super().keyPressEvent(event)

    def show_loading_message(self):
        """Show loading message with error handling"""
        try:
            if self.message_box is None:
                self.message_box = QMessageBox(self)
                self.message_box.setIcon(QMessageBox.Information)
                self.message_box.setText("در حال آماده‌سازی...")
                self.message_box.setStandardButtons(QMessageBox.NoButton)
                close_button = self.message_box.addButton("بستن", QMessageBox.RejectRole)
                close_button.setStyleSheet("background-color: #f9f9f9; color: #333; font-size: 14px;")
                close_button.clicked.connect(self.hide_loading_message)
                self.message_box.show()
        except Exception as e:
            logger.error(f"Error showing loading message: {e}")

    def hide_loading_message(self):
        """Hide loading message with error handling"""
        try:
            if self.message_box:
                self.message_box.close()
                self.message_box = None
        except Exception as e:
            logger.error(f"Error hiding loading message: {e}")

    def auto_complete(self):
        """Auto-complete with comprehensive error handling"""
        try:
            if not self.auto_complete_enabled:
                return
                
            current_text = self.toPlainText().strip()

            # Prevent processing of very long texts
            if len(current_text) > self.max_text_length:
                logger.warning("Text too long for auto-complete")
                return

            if (not current_text or 
                current_text == self.last_text or 
                not self.text_was_changed):
                return

            self.last_text = current_text
            self.text_was_changed = False

            self.show_loading_message()

            # Stop previous thread if running
            if self.auto_complete_thread and self.auto_complete_thread.isRunning():
                self.auto_complete_thread.stop()

            self.auto_complete_thread = SafeAutoCompleteThread(self.ai_manager, current_text)
            self.auto_complete_thread.finished.connect(self.on_auto_complete_finished)
            self.auto_complete_thread.error_occurred.connect(self.on_auto_complete_error)
            self.auto_complete_thread.start()

        except Exception as e:
            logger.error(f"Error in auto_complete: {e}")
            self.hide_loading_message()

    def on_auto_complete_finished(self, response: str):
        """Handle auto-complete finished with error handling"""
        try:
            if response and not response.startswith("خطا"):
                self.setPlainText(response)
            else:
                QMessageBox.warning(self, "خطا", "خطا در دریافت پاسخ از AI.")
        except Exception as e:
            logger.error(f"Error in on_auto_complete_finished: {e}")
        finally:
            self.hide_loading_message()

    def on_auto_complete_error(self, error_message: str):
        """Handle auto-complete error"""
        try:
            QMessageBox.warning(self, "خطا", error_message)
        except Exception as e:
            logger.error(f"Error in on_auto_complete_error: {e}")
        finally:
            self.hide_loading_message()

    def focusOutEvent(self, event):
        """Handle focus out with error handling"""
        try:
            self.timer.stop()
            super().focusOutEvent(event)
        except Exception as e:
            logger.error(f"Error in focusOutEvent: {e}")
            super().focusOutEvent(event)

    def closeEvent(self, event):
        """Handle close event with cleanup"""
        try:
            if self.auto_complete_thread and self.auto_complete_thread.isRunning():
                self.auto_complete_thread.stop()
            self.hide_loading_message()
        except Exception as e:
            logger.error(f"Error in closeEvent: {e}")
        finally:
            event.accept()


class SafeAskAIThread(QThread):
    """Thread-safe AI asking with error handling"""
    
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, ai_manager, prompt: str):
        super().__init__()
        self.ai_manager = ai_manager
        self.prompt = prompt
        self._running = True

    def run(self):
        """Run AI request with error handling"""
        try:
            if not self._running:
                return
                
            response = self.ai_manager.get_ai_response(self.prompt)
            
            if self._running:
                self.finished.emit(response)

        except Exception as e:
            logger.error(f"Error in AI request: {e}")
            if self._running:
                self.error_occurred.emit(f"خطا در دریافت پاسخ از AI: {str(e)}")

    def stop(self):
        """Stop the thread safely"""
        self._running = False
        self.wait()


class SafeMainWindow(QMainWindow):
    """Thread-safe main window with comprehensive error handling and anti-crash mechanisms"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize with error handling
        try:
            self._init_ui()
            self._init_components()
            self._init_connections()
            logger.info("MainWindow initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing MainWindow: {e}")
            self._show_error_dialog("خطا در راه‌اندازی برنامه", str(e))

    def _init_ui(self):
        """Initialize UI components with error handling"""
        try:
            self.setWindowTitle("CodePrime")
            self.setGeometry(100, 100, 900, 600)  
            self.text_processed = False
            
            # Set up Persian fonts
            self.persian_font_family = setup_persian_fonts(QApplication.instance())
            
            # Create status bar
            self.status_bar = QStatusBar()
            self.setStatusBar(self.status_bar)
            self.status_bar.showMessage("آماده")
            
            # Create progress bar
            self.progress_bar = QProgressBar()
            self.progress_bar.setVisible(False)
            self.status_bar.addPermanentWidget(self.progress_bar)
            
            # Create fullscreen button
            self._create_fullscreen_button()
            
            # Create toolbar
            self._create_toolbar()
            
            # Create stylesheet
            self._create_stylesheet()
            
            # Set layout direction
            self.setLayoutDirection(Qt.RightToLeft)
            
            # Create tab widget
            self._create_tab_widget()
            
            # Create shortcuts
            self._create_shortcuts()
            
        except Exception as e:
            logger.error(f"Error in _init_ui: {e}")
            raise

    def _create_fullscreen_button(self):
        """Create fullscreen button with error handling"""
        try:
            self.fullscreen_button = QPushButton("🖥️ تمام صفحه")
            self.fullscreen_button.setStyleSheet("""
                QPushButton {
                    background-color: #9400d3;
                    color: white;
                    border: none;
                    padding: 5px;
                    font-size: 12px;
                    border-radius: 3px;
                    margin: 2px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        except Exception as e:
            logger.error(f"Error creating fullscreen button: {e}")
        
    def _create_toolbar(self):
        """Create toolbar with error handling"""
        try:
            self.toolbar = self.addToolBar("Main Toolbar")
            self.toolbar.setMovable(False)
            self.toolbar.addWidget(self.fullscreen_button)
        except Exception as e:
            logger.error(f"Error creating toolbar: {e}")

    def _create_stylesheet(self):
        """Create comprehensive stylesheet with error handling"""
        try:
            self.setStyleSheet(f"""
            QMainWindow {{
            background-color: #f8f9fa;
                font-family: {self.persian_font_family};
            }}
            QLabel {{
            font-size: 13px;
            color: #2c3e50;
            padding: 5px;
                font-family: {self.persian_font_family};
            }}
            QPushButton {{
            background-color: #6c5ce7;
            color: white;
            border: none;
            padding: 8px 15px;
            font-size: 13px;
            border-radius: 5px;
            margin: 3px;
            font-weight: bold;
                font-family: {self.persian_font_family};
            }}
            QPushButton:hover {{
            background-color: #5b4bc4;
            }}
            QPushButton:pressed {{
            background-color: #4a3db3;
            }}
            QTextEdit, QLineEdit {{
            background-color: white;
            border: 2px solid #e0e0e0;
            padding: 8px;
            font-size: 13px;
            border-radius: 5px;
                font-family: {self.persian_font_family};
            }}
            QTextEdit:focus, QLineEdit:focus {{
            border: 2px solid #6c5ce7;
            }}
            QListWidget {{
            background-color: white;
            border: 2px solid #e0e0e0;
            padding: 5px;
            font-size: 13px;
            border-radius: 5px;
                font-family: {self.persian_font_family};
            }}
            QTabWidget::pane {{
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            background-color: #f8f9fa;
            }}
            QTabBar::tab {{
            padding: 8px 15px;
            margin: 2px;
            font-size: 13px;
            background-color: #f1f3f5;
            border: 1px solid #e0e0e0;
            border-top-left-radius: 5px;
            border-top-right-radius: 5px;
                font-family: {self.persian_font_family};
            }}
            QTabBar::tab:selected {{
            background-color: #6c5ce7;
            color: white;
            }}
            QTabBar::tab:hover:!selected {{
            background-color: #e9ecef;
            }}
            QComboBox {{
            padding: 5px;
            border: 2px solid #e0e0e0;
            border-radius: 5px;
            background-color: white;
                font-family: {self.persian_font_family};
            font-size: 13px;
            }}
            QComboBox:hover {{
            border: 2px solid #6c5ce7;
            }}
            QComboBox::drop-down {{
            border: none;
            }}
            QComboBox::down-arrow {{
            image: url(down_arrow.png);
            width: 12px;
            height: 12px;
            }}
            QScrollBar:vertical {{
            border: none;
            background: #f1f3f5;
            width: 10px;
            margin: 0px;
            }}
            QScrollBar::handle:vertical {{
            background: #6c5ce7;
            min-height: 20px;
            border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            }}
            QScrollBar:horizontal {{
            border: none;
            background: #f1f3f5;
            height: 10px;
            margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
            background: #6c5ce7;
            min-width: 20px;
            border-radius: 5px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            }}
            QMessageBox {{
                font-family: {self.persian_font_family};
            }}
            QMessageBox QLabel {{
                font-family: {self.persian_font_family};
            }}
            QMessageBox QPushButton {{
                font-family: {self.persian_font_family};
            }}
            QInputDialog {{
                font-family: {self.persian_font_family};
            }}
            QInputDialog QLabel {{
                font-family: {self.persian_font_family};
            }}
            QInputDialog QLineEdit {{
                font-family: {self.persian_font_family};
            }}
            QInputDialog QPushButton {{
                font-family: {self.persian_font_family};
            }}
            QFileDialog {{
                font-family: {self.persian_font_family};
            }}
            QFileDialog QLabel {{
                font-family: {self.persian_font_family};
            }}
            QFileDialog QPushButton {{
                font-family: {self.persian_font_family};
            }}
            QFileDialog QLineEdit {{
                font-family: {self.persian_font_family};
            }}
            QFileDialog QComboBox {{
                font-family: {self.persian_font_family};
            }}
            QFileDialog QListWidget {{
                font-family: {self.persian_font_family};
            }}
            QFileDialog QTreeWidget {{
                font-family: {self.persian_font_family};
            }}
            QStatusBar {{
                font-family: {self.persian_font_family};
            }}
            QProgressBar {{
                font-family: {self.persian_font_family};
            }}
        """)
        except Exception as e:
            logger.error(f"Error creating stylesheet: {e}")

    def _create_tab_widget(self):
        """Create tab widget with error handling"""
        try:
            self.tabs = QTabWidget(self)
            self.tabs.setStyleSheet(f"""
                QTabWidget::pane {{
                border: 1px solid #ccc;
                border-radius: 3px;
                }}
                QTabBar::tab {{
                padding: 5px 10px;
                margin: 2px;
                font-size: 12px;
                    font-family: {self.persian_font_family};
                }}
            """)
            self.setCentralWidget(self.tabs)
        except Exception as e:
            logger.error(f"Error creating tab widget: {e}")
        
    def _create_shortcuts(self):
        """Create keyboard shortcuts with error handling"""
        try:
            self.shortcut = QShortcut(QKeySequence("F11"), self)
            self.shortcut.activated.connect(self.toggle_fullscreen)
            
            self.esc_shortcut = QShortcut(QKeySequence("Esc"), self)
            self.esc_shortcut.activated.connect(self.exit_fullscreen)
        except Exception as e:
            logger.error(f"Error creating shortcuts: {e}")

    def _init_components(self):
        """Initialize all components with error handling"""
        try:
            # Initialize managers and components
            self.file_manager = SafeFileManager()
            self.settings_manager = SettingsManager()
            self.ai_manager = AIManager(api_key="FAKE")
            self.code_editor = SafeCodeEditor(self.ai_manager)
            self.interpreter_editor = QTextEdit()  
            self.interpreter_editor.setPlaceholderText("$: ....")

            # Initialize collaboration client
            self.collab_client = SafeCollaborationClient(self.code_editor)
            
            # Initialize data structures
            self.tasks = []
            self.sessions_log = []
            self.current_file = None
            self.session_start_time = 0
            self.project_path = None
            self.repo = None
            
            # Create all tabs
            self._create_all_tabs()
            
            # Set window icon
            self._set_window_icon()
            
        except Exception as e:
            logger.error(f"Error in _init_components: {e}")
            raise

    def _create_all_tabs(self):
        """Create all tabs with error handling"""
        try:
            self.create_task_tab()
            self.create_git_tab()
            self.create_ai_tab()
            self.create_code_editor_tab()
            self.create_interpreter_tab()
            self.create_terminal_tab()  
            self.create_file_browser_tab()
            self.create_project_management_tab()
            self.create_settings_tab()
            self.create_about_tab()
            self.create_vision_tab()
        except Exception as e:
            logger.error(f"Error creating tabs: {e}")

    def _set_window_icon(self):
        """Set window icon with error handling"""
        try:
            icon_path = "gui/app_icon.png"
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            logger.error(f"Error setting window icon: {e}")

    def _init_connections(self):
        """Initialize signal connections with error handling"""
        try:
            # Connect collaboration client using settings
            websocket_config = self.settings_manager.get_websocket_config()
            client_url = websocket_config.get("client_url", "ws://127.0.0.1:8765")
            self.collab_client.connect(client_url)
            self.code_editor.textChanged.connect(self.send_changes)
            
            # Connect timers
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.check_deadlines)
            self.timer.start(60000)  

            self.session_timer = QTimer(self)
            self.session_timer.timeout.connect(self.update_session_time)

        except Exception as e:
            logger.error(f"Error in _init_connections: {e}")

    def _show_error_dialog(self, title: str, message: str):
        """Show error dialog with error handling"""
        try:
            QMessageBox.critical(self, title, message)
        except Exception as e:
            logger.error(f"Error showing error dialog: {e}")

    def _show_success_dialog(self, title: str, message: str):
        """Show success dialog with error handling"""
        try:
            QMessageBox.information(self, title, message)
        except Exception as e:
            logger.error(f"Error showing success dialog: {e}")

    def _show_warning_dialog(self, title: str, message: str):
        """Show warning dialog with error handling"""
        try:
            QMessageBox.warning(self, title, message)
        except Exception as e:
            logger.error(f"Error showing warning dialog: {e}")

    def toggle_fullscreen(self):
        """Toggle fullscreen with error handling"""
        try:
            if self.isFullScreen():
                self.exit_fullscreen()
            else:
                self.showFullScreen()
                self.fullscreen_button.setText("🖥️ خروج از تمام صفحه")
                self.fullscreen_button.setToolTip("خروج از حالت تمام صفحه (Esc)")
        except Exception as e:
            logger.error(f"Error toggling fullscreen: {e}")

    def exit_fullscreen(self):
        """Exit fullscreen with error handling"""
        try:
            if self.isFullScreen():
                self.showNormal()
                self.fullscreen_button.setText("🖥️ تمام صفحه")
                self.fullscreen_button.setToolTip("حالت تمام صفحه (F11)")
        except Exception as e:
            logger.error(f"Error exiting fullscreen: {e}")

    def send_changes(self):
        """Send changes with error handling"""
        try:
            if not self.collab_client.is_receiving:
                text = self.code_editor.toPlainText()
                self.collab_client.send_message(text)
        except Exception as e:
            logger.error(f"Error sending changes: {e}")

    def closeEvent(self, event):
        """Handle close event with cleanup"""
        try:
            # Stop all timers
            if hasattr(self, 'timer'):
                self.timer.stop()
            if hasattr(self, 'session_timer'):
                self.session_timer.stop()
            
            # Stop collaboration client
            if hasattr(self, 'collab_client'):
                self.collab_client.close()
            
            # Stop vision manager
            if hasattr(self, 'vision_manager'):
                self.vision_manager.stop_vision()
            
            # Stop session
            self.stop_session()
            
            # Clear file cache
            if hasattr(self, 'file_manager'):
                self.file_manager.clear_cache()
            
            logger.info("Application closed successfully")
            
        except Exception as e:
            logger.error(f"Error in closeEvent: {e}")
        finally:
            event.accept()

    def create_about_tab(self):
        """Create about tab with error handling"""
        try:
            about_tab = QWidget()
            about_layout = QVBoxLayout()
            about_layout.setSpacing(15)
            about_layout.setContentsMargins(15, 15, 15, 15)

            # Main Title with gradient effect
            title_label = QLabel("🚀 CodePrime IDE")
            title_label.setStyleSheet("""
                font-size: 28px;
                font-weight: bold;
                color: #ffffff;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #667eea, stop:1 #764ba2);
                padding: 20px;
                border-radius: 12px;
                border: 2px solid #5a6fd8;
                margin-bottom: 15px;
            """)
            title_label.setAlignment(Qt.AlignCenter)
            about_layout.addWidget(title_label)

            # Subtitle
            subtitle_label = QLabel("محیط توسعه یکپارچه هوشمند")
            subtitle_label.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                background-color: #ecf0f1;
                padding: 12px;
                border-radius: 8px;
                border: 2px solid #bdc3c7;
                margin-bottom: 15px;
            """)
            subtitle_label.setAlignment(Qt.AlignCenter)
            about_layout.addWidget(subtitle_label)

            # Create a scroll area for better fullscreen support
            scroll_widget = QWidget()
            scroll_layout = QVBoxLayout()
            scroll_layout.setSpacing(12)
            scroll_layout.setContentsMargins(5, 5, 5, 5)

            # Developer Info Card
            dev_card = QWidget()
            dev_card.setStyleSheet("""
                QWidget {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #f8f9fa, stop:1 #e9ecef);
                    border: 2px solid #dee2e6;
                    border-radius: 10px;
                    padding: 3px;
                }
            """)
            dev_layout = QVBoxLayout()
            dev_layout.setSpacing(5)
            
            dev_title = QLabel("👨‍💻 توسعه‌دهنده")
            dev_title.setStyleSheet("""
                font-size: 18px;
                font-weight: bold;
                color: #495057;
                margin-bottom: 5px;
            """)
            dev_title.setAlignment(Qt.AlignCenter)
            dev_layout.addWidget(dev_title)
            
            dev_info = QLabel("علی جعفری")
            dev_info.setStyleSheet("""
                font-size: 16px;
                color: #6c757d;
                margin-bottom: 3px;
            """)
            dev_info.setAlignment(Qt.AlignCenter)
            dev_layout.addWidget(dev_info)
            
            dev_card.setLayout(dev_layout)
            scroll_layout.addWidget(dev_card)

            # Version Info Card
            version_card = QWidget()
            version_card.setStyleSheet("""
                QWidget {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #e3f2fd, stop:1 #bbdefb);
                    border: 2px solid #90caf9;
                    border-radius: 10px;
                    padding: 3px;
                }
            """)
            version_layout = QVBoxLayout()
            version_layout.setSpacing(5)
            
            version_title = QLabel("📋 اطلاعات نسخه")
            version_title.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
                color: #1565c0;
                margin-bottom: 5px;
            """)
            version_title.setAlignment(Qt.AlignCenter)
            version_layout.addWidget(version_title)
            
            version_info = QLabel("نسخه: 1.0.0\nتاریخ انتشار: ۱۴۰۳ / ۱۴۰۴")
            version_info.setStyleSheet("""
                font-size: 14px;
                color: #1976d2;
                margin-bottom: 3px;
            """)
            version_info.setAlignment(Qt.AlignCenter)
            version_layout.addWidget(version_info)
            
            version_card.setLayout(version_layout)
            scroll_layout.addWidget(version_card)

            # Website Section
            website_card = QWidget()
            website_card.setStyleSheet("""
                QWidget {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #f3e5f5, stop:1 #e1bee7);
                    border: 2px solid #ce93d8;
                    border-radius: 10px;
                    padding: 3px;
                }
            """)
            website_layout = QVBoxLayout()
            website_layout.setSpacing(5)
            
            website_title = QLabel("🌐 وب‌سایت رسمی")
            website_title.setStyleSheet("""
                font-size: 18px;
                font-weight: bold;
                color: #7b1fa2;
                margin-bottom: 5px;
            """)
            website_title.setAlignment(Qt.AlignCenter)
            website_layout.addWidget(website_title)
            
            website_url = QLabel("www.ali-folio.ir")
            website_url.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
                color: #9c27b0;
                margin-bottom: 8px;
                padding: 8px;
                background-color: rgba(255,255,255,0.7);
                border-radius: 6px;
            """)
            website_url.setAlignment(Qt.AlignCenter)
            website_layout.addWidget(website_url)
            
            dns_warning = QLabel("⚠️ توجه: برای دسترسی به سایت از DNS استفاده کنید (سایت فیلتر است)")
            dns_warning.setStyleSheet("""
                font-size: 12px;
                color: #d32f2f;
                background-color: rgba(255,255,255,0.8);
                padding: 6px;
                border-radius: 5px;
                border: 1px solid #f44336;
            """)
            dns_warning.setAlignment(Qt.AlignCenter)
            dns_warning.setWordWrap(True)
            website_layout.addWidget(dns_warning)
            
            website_card.setLayout(website_layout)
            scroll_layout.addWidget(website_card)

            # Features Section
            features_card = QWidget()
            features_card.setStyleSheet("""
                QWidget {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #e8f5e8, stop:1 #c8e6c9);
                    border: 2px solid #a5d6a7;
                    border-radius: 10px;
                    padding: 3px;
                }
            """)
            features_layout = QVBoxLayout()
            features_layout.setSpacing(5)
            
            features_title = QLabel("✨ قابلیت‌های کلیدی")
            features_title.setStyleSheet("""
                font-size: 16px;
                font-weight: bold;
                color: #2e7d32;
                margin-bottom: 5px;
            """)
            features_title.setAlignment(Qt.AlignCenter)
            features_layout.addWidget(features_title)
            
            features_list = QLabel("• ویرایشگر کد هوشمند\n• پشتیبانی از AI\n• همکاری آنلاین\n• مدیریت پروژه\n• کنترل نسخه Git\n• تایپ با حرکات دست")
            features_list.setStyleSheet("""
                font-size: 12px;
                color: #388e3c;
                margin-bottom: 3px;
                padding: 8px;
                background-color: rgba(255,255,255,0.7);
                border-radius: 6px;
            """)
            features_list.setAlignment(Qt.AlignCenter)
            features_layout.addWidget(features_list)
            
            features_card.setLayout(features_layout)
            scroll_layout.addWidget(features_card)

            # Buttons Section
            button_layout = QHBoxLayout()
            button_layout.setSpacing(10)
            
            website_button = QPushButton("🌐 بازدید از وب‌سایت")
            website_button.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: bold;
                    color: white;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #667eea, stop:1 #764ba2);
                    padding: 12px 25px;
                    border-radius: 20px;
                    border: 2px solid #5a6fd8;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #5a6fd8, stop:1 #6a4c93);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #4a5fc8, stop:1 #5a3c83);
                }
            """)
            website_button.clicked.connect(self.open_website)
            
            github_button = QPushButton("📧 تماس با ما")
            github_button.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: bold;
                    color: white;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #f093fb, stop:1 #f5576c);
                    padding: 12px 25px;
                    border-radius: 20px;
                    border: 2px solid #e91e63;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #e91e63, stop:1 #d81b60);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #c2185b, stop:1 #ad1457);
                }
            """)
            github_button.clicked.connect(self.contact_us)
            
            button_layout.addWidget(website_button)
            button_layout.addWidget(github_button)
            scroll_layout.addLayout(button_layout)

            # Footer
            footer_label = QLabel("با ❤️ ساخته شده در ایران")
            footer_label.setStyleSheet("""
                font-size: 12px;
                color: #6c757d;
                padding: 8px;
                background-color: #f8f9fa;
                border-radius: 6px;
                border: 1px solid #dee2e6;
            """)
            footer_label.setAlignment(Qt.AlignCenter)
            scroll_layout.addWidget(footer_label)

            # Add stretch to push content to top
            scroll_layout.addStretch()

            scroll_widget.setLayout(scroll_layout)
            
            # Create scroll area
            scroll_area = QScrollArea()
            scroll_area.setWidget(scroll_widget)
            scroll_area.setWidgetResizable(True)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_area.setStyleSheet("""
                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
                QScrollBar:vertical {
                    background-color: #f0f0f0;
                    width: 12px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background-color: #c0c0c0;
                    border-radius: 6px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #a0a0a0;
                }
            """)

            about_layout.addWidget(scroll_area)
            about_tab.setLayout(about_layout)
            self.tabs.addTab(about_tab, "درباره ما")
            
        except Exception as e:
            logger.error(f"Error creating about tab: {e}")

    def open_website(self):
        """Open website with error handling"""
        try:
            webbrowser.open("https://www.ali-folio.ir/")
        except Exception as e:
            logger.error(f"Error opening website: {e}")
            self._show_error_dialog("خطا", "خطا در باز کردن وب‌سایت")

    def contact_us(self):
        """Contact us with error handling"""
        try:
            contact_info = """
📧 اطلاعات تماس:

🌐 وب‌سایت: www.ali-folio.ir
📧 ایمیل: info@ali-folio.ir
📱 تلگرام: @ali_folio

⚠️ توجه: برای دسترسی به سایت از DNS استفاده کنید
            """
            QMessageBox.information(self, "اطلاعات تماس", contact_info)
        except Exception as e:
            logger.error(f"Error showing contact info: {e}")
            self._show_error_dialog("خطا", "خطا در نمایش اطلاعات تماس")

    def create_terminal_tab(self):
        """Create terminal tab with error handling"""
        try:
            terminal_tab = QWidget()
            terminal_layout = QVBoxLayout()

            self.terminal_input = QLineEdit()
            self.terminal_input.setPlaceholderText("دستور خود را وارد کنید...")
            self.terminal_input.returnPressed.connect(self.execute_command)

            self.terminal_output = QTextEdit()
            self.terminal_output.setReadOnly(True)
            self.terminal_output.setStyleSheet("background-color: black; color: white; font-family: monospace;")

            terminal_layout.addWidget(QLabel("💻 ترمینال:"))
            terminal_layout.addWidget(self.terminal_input)
            terminal_layout.addWidget(self.terminal_output)

            terminal_tab.setLayout(terminal_layout)
            self.tabs.addTab(terminal_tab, "ترمینال")
            
        except Exception as e:
            logger.error(f"Error creating terminal tab: {e}")

    def execute_command(self):
        """Execute terminal command with error handling"""
        try:
            command = self.terminal_input.text()
            if not command.strip():
                return

            self.terminal_output.append(f"$ {command}")

            # Show progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            self.status_bar.showMessage("در حال اجرای دستور...")

            try:
                result = subprocess.run(
                    command, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=30  # 30 second timeout
                )
                output = result.stdout if result.stdout else result.stderr
                self.terminal_output.append(output)
            except subprocess.TimeoutExpired:
                self.terminal_output.append("❌ خطا: دستور بیش از 30 ثانیه طول کشید")

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            self.terminal_output.append(f"❌ خطای سیستمی: {str(e)}")
        finally:
            self.progress_bar.setVisible(False)
            self.status_bar.showMessage("آماده")
            self.terminal_input.clear()

    def create_file_browser_tab(self):
        """Create file browser tab with error handling"""
        try:
            file_browser_tab = QWidget()
            file_browser_layout = QVBoxLayout()

            self.file_list = QListWidget()
            self.file_list.setStyleSheet("font-size: 14px; padding: 5px; border-radius: 5px;")

            self.load_files_button = QPushButton("بارگذاری فایل‌ها")
            self.load_files_button.clicked.connect(self.load_files)

            file_browser_layout.addWidget(QLabel("📂 فایل‌های پروژه:"))
            file_browser_layout.addWidget(self.file_list)
            file_browser_layout.addWidget(self.load_files_button)

            file_browser_tab.setLayout(file_browser_layout)
            self.tabs.addTab(file_browser_tab, "مرورگر فایل‌ها")

            self.file_list.itemClicked.connect(self.open_file)
            
        except Exception as e:
            logger.error(f"Error creating file browser tab: {e}")

    def load_files(self):
        """Load files with error handling"""
        try:
            project_path = QFileDialog.getExistingDirectory(self, "انتخاب پروژه")
            if project_path:
                self.progress_bar.setVisible(True)
                self.progress_bar.setRange(0, 0)
                self.status_bar.showMessage("در حال بارگذاری فایل‌ها...")
                
                self.file_list.clear()
                files = self.file_manager.get_all_files(project_path)
                
                for file in files:
                    self.file_list.addItem(file)
                
                self.status_bar.showMessage(f"{len(files)} فایل بارگذاری شد")
                
        except Exception as e:
            logger.error(f"Error loading files: {e}")
            self._show_error_dialog("خطا", f"خطا در بارگذاری فایل‌ها:\n{str(e)}")
        finally:
            self.progress_bar.setVisible(False)

    def open_file(self, item):
        """Open file with error handling"""
        try:
            file_path = item.text()  
            self.current_file = file_path

            # Validate file path
            if not os.path.exists(file_path):
                self._show_error_dialog("خطا", "فایل مورد نظر یافت نشد")
                return

            # Check file size (prevent loading very large files)
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                self._show_warning_dialog("هشدار", "فایل بسیار بزرگ است و ممکن است کند بارگذاری شود")

            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.status_bar.showMessage("در حال باز کردن فایل...")

            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
                self.code_editor.setPlainText(content)
                self.code_editor.set_syntax_highlighting("Python")  

            self.tabs.setCurrentIndex(3)  # Switch to code editor tab
            self.start_session()
            self.status_bar.showMessage(f"فایل {os.path.basename(file_path)} باز شد")

        except UnicodeDecodeError:
            self._show_error_dialog("خطا", "فایل با رمزگذاری نامعتبر است")
        except Exception as e:
            logger.error(f"Error opening file: {e}")
            self._show_error_dialog("خطا", f"خطا در باز کردن فایل:\n{str(e)}")
        finally:
            self.progress_bar.setVisible(False)

    def create_code_editor_tab(self):
        """Create code editor tab with error handling"""
        try:
            code_editor_tab = QWidget()
            code_editor_layout = QVBoxLayout()

            self.save_code_button = QPushButton("💾 ذخیره فایل")
            self.save_code_button.clicked.connect(self.save_file)

            code_editor_layout.addWidget(QLabel("👨‍💻 ویرایشگر کد:"))
            code_editor_layout.addWidget(self.code_editor)
            code_editor_layout.addWidget(self.save_code_button)

            code_editor_tab.setLayout(code_editor_layout)
            self.tabs.addTab(code_editor_tab, "ویرایشگر کد")

        except Exception as e:
            logger.error(f"Error creating code editor tab: {e}")

    def save_file(self):
        """Save file with error handling"""
        try:
            if self.current_file:
                file_path = self.current_file
            else:
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "ذخیره فایل", "", "Python Files (*.py);;All Files (*)")
            if not file_path:
                return  

            # Create backup
            if os.path.exists(file_path):
                backup_path = file_path + ".backup"
                try:
                    import shutil
                    shutil.copy2(file_path, backup_path)
                except Exception as e:
                    logger.warning(f"Could not create backup: {e}")

            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.status_bar.showMessage("در حال ذخیره فایل...")

            with open(file_path, "w", encoding="utf-8") as file:
                file.write(self.code_editor.toPlainText())

            self._show_success_dialog("ذخیره شد", f"فایل با موفقیت در '{file_path}' ذخیره شد.")
            self.status_bar.showMessage("فایل ذخیره شد")

        except Exception as e:
            logger.error(f"Error saving file: {e}")
            self._show_error_dialog("خطا", f"خطا در ذخیره‌سازی فایل:\n{str(e)}")
        finally:
            self.progress_bar.setVisible(False)
    
    def start_session(self):
        """Start session with error handling"""
        try:
            self.session_start_time = time.time()
            self.session_timer.start(1000)
        except Exception as e:
            logger.error(f"Error starting session: {e}")

    def stop_session(self):
        """Stop session with error handling"""
        try:
            self.session_timer.stop()
            if self.session_start_time > 0:
                session_duration = time.time() - self.session_start_time 
                self.sessions_log.append(f"مدت زمان جلسه: {self.format_time(session_duration)}")
                self.save_sessions_log() 
        except Exception as e:
            logger.error(f"Error stopping session: {e}")

    def format_time(self, seconds):
        """Format time with error handling"""
        try:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            seconds = int(seconds % 60)
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        except Exception as e:
            logger.error(f"Error formatting time: {e}")
            return "00:00:00"

    def save_sessions_log(self):
        """Save sessions log with error handling"""
        try:
            log_file_path = "sessions_log.txt"
            with open(log_file_path, "a", encoding="utf-8") as log_file:
                for log in self.sessions_log:
                    log_file.write(log + "\n")
                self.sessions_log.clear()  
        except Exception as e:
            logger.error(f"Error saving sessions log: {e}")

    def update_session_time(self):
        """Update session time with error handling"""
        try:
            if self.session_start_time > 0:
                elapsed_time = time.time() - self.session_start_time
                formatted_duration = self.format_time(elapsed_time)
                self.status_bar.showMessage(f"زمان جلسه: {formatted_duration}")
        except Exception as e:
            logger.error(f"Error updating session time: {e}")

    def create_interpreter_tab(self):
        """Create interpreter tab with error handling"""
        try:
            interpreter_tab = QWidget()
            layout = QVBoxLayout()

            self.run_code_button = QPushButton("▶ اجرای کد")
            self.run_code_button.clicked.connect(self.run_python_code)

            self.output_display = QTextEdit()
            self.output_display.setReadOnly(True)

            layout.addWidget(QLabel("👨‍💻 مفسر پایتون:"))
            layout.addWidget(self.interpreter_editor)
            layout.addWidget(self.run_code_button)
            layout.addWidget(QLabel("📜 خروجی:"))
            layout.addWidget(self.output_display)

            interpreter_tab.setLayout(layout)
            self.tabs.addTab(interpreter_tab, "🐍 مفسر پایتون")
            
        except Exception as e:
            logger.error(f"Error creating interpreter tab: {e}")

    def run_python_code(self):
        """Run Python code with error handling"""
        try:
            code = self.interpreter_editor.toPlainText() 
            if not code.strip():
                self.output_display.setText("⚠ لطفاً کد وارد کنید!")
                return

            # Check code length
            if len(code) > 10000:
                self._show_warning_dialog("هشدار", "کد بسیار طولانی است")
                return

            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.status_bar.showMessage("در حال اجرای کد...")

            old_stdout = sys.stdout
            redirected_output = io.StringIO()
            sys.stdout = redirected_output

            try:
                # Create safe execution environment
                safe_globals = {
                    '__builtins__': {
                        'print': print,
                        'len': len,
                        'str': str,
                        'int': int,
                        'float': float,
                        'list': list,
                        'dict': dict,
                        'tuple': tuple,
                        'set': set,
                        'range': range,
                        'enumerate': enumerate,
                        'zip': zip,
                        'map': map,
                        'filter': filter,
                        'sum': sum,
                        'max': max,
                        'min': min,
                        'abs': abs,
                        'round': round,
                        'sorted': sorted,
                        'reversed': reversed,
                        'any': any,
                        'all': all,
                        'isinstance': isinstance,
                        'type': type,
                        'dir': dir,
                        'help': help,
                        'open': open,
                        'input': input,
                    }
                }
                
                exec(code, safe_globals)
                output_text = redirected_output.getvalue() or "✅ کد بدون خروجی اجرا شد."
                
            except Exception as e:
                output_text = f"❌ خطا:\n{str(e)}"
            finally:
                sys.stdout = old_stdout

            self.output_display.setText(output_text)
            self.status_bar.showMessage("کد اجرا شد")

        except Exception as e:
            logger.error(f"Error running Python code: {e}")
            self.output_display.setText(f"❌ خطای سیستمی:\n{str(e)}")
        finally:
            self.progress_bar.setVisible(False)

    def create_task_tab(self):
        """Create task tab with error handling"""
        try:
            task_tab = QWidget()
            task_layout = QVBoxLayout()

            self.task_list = QListWidget()
            self.task_list.setStyleSheet("border-radius: 5px; padding: 5px;")

            self.add_task_button = QPushButton("➕ افزودن تسک")
            self.remove_task_button = QPushButton("❌ حذف تسک")

            self.add_task_button.clicked.connect(self.add_task)
            self.remove_task_button.clicked.connect(self.remove_task)

            task_layout.addWidget(QLabel("📌 لیست تسک‌ها:"))
            task_layout.addWidget(self.task_list)
            task_layout.addWidget(self.add_task_button)
            task_layout.addWidget(self.remove_task_button)

            task_tab.setLayout(task_layout)
            self.tabs.addTab(task_tab, "📝 تسک‌ها")
            
        except Exception as e:
            logger.error(f"Error creating task tab: {e}")

    def add_task(self):
        """Add task with error handling"""
        try:
            task_name, ok = QInputDialog.getText(self, "افزودن تسک", "نام تسک جدید:")
            if ok and task_name:
                deadline_hours, ok = QInputDialog.getDouble(
                    self, "ددلاین تسک", "چند ساعت دیگر؟", min=0.1, max=8760)  # Max 1 year
                if ok:
                    deadline = QDateTime.currentDateTime().addSecs(int(deadline_hours * 3600))
                    self.tasks.append((task_name, deadline))
                    self.task_list.addItem(f"{task_name} - ددلاین: {deadline.toString('hh:mm yyyy/MM/dd')}")
        except Exception as e:
            logger.error(f"Error adding task: {e}")

    def remove_task(self):
        """Remove task with error handling"""
        try:
            selected_item = self.task_list.currentRow()
            if selected_item >= 0:
                self.task_list.takeItem(selected_item)
                del self.tasks[selected_item]
        except Exception as e:
            logger.error(f"Error removing task: {e}")

    def check_deadlines(self):
        """Check deadlines with error handling"""
        try:
            now = QDateTime.currentDateTime()
            for i, (task_name, deadline) in enumerate(self.tasks):
                if now >= deadline:
                    item = self.task_list.item(i)
                    if item:
                        item.setForeground(Qt.red)
                        item.setText(f"⏳ {task_name} - **منقضی شده!**")
        except Exception as e:
            logger.error(f"Error checking deadlines: {e}")

    def create_git_tab(self):
        """Create git tab with error handling"""
        try:
            git_tab = QWidget()
            git_layout = QVBoxLayout()
            git_layout.setSpacing(0)
            git_layout.setContentsMargins(0, 0, 0, 0)

            title_label = QLabel("مدیریت گیت:") 
            title_label.setStyleSheet("""
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 10px;
            """)

            git_layout.addWidget(title_label)

            self.commit_button = QPushButton("Commit انجام")
            self.push_button = QPushButton("Push انجام")
            self.pull_button = QPushButton("Pull انجام")
            self.status_button = QPushButton("Git بررسی وضعیت")

            for button in [self.commit_button, self.push_button, self.pull_button, self.status_button]:
                button.setMinimumHeight(40)
                button.setStyleSheet("""
                    QPushButton {
                        margin: 6px;
                        padding: 10px;
                        background-color: #9400d3;
                        color: white;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                """)

            self.commit_button.clicked.connect(self.git_commit)
            self.push_button.clicked.connect(self.git_push)
            self.pull_button.clicked.connect(self.git_pull)
            self.status_button.clicked.connect(self.git_status)

            git_layout.addStretch()
            git_layout.addWidget(self.commit_button)
            git_layout.addWidget(self.push_button)
            git_layout.addWidget(self.pull_button)
            git_layout.addWidget(self.status_button)

            git_tab.setLayout(git_layout)
            self.tabs.addTab(git_tab, "گیت")
            
        except Exception as e:
            logger.error(f"Error creating git tab: {e}")

    def create_ai_tab(self):
        """Create AI tab with error handling"""
        try:
            ai_tab = QWidget()
            ai_layout = QVBoxLayout()

            self.ai_label = QLabel("پرسش خود را از AI بپرسید:")
            self.ai_input = QLineEdit()
            self.ai_input.setPlaceholderText("متن خود را وارد کنید...")
            self.ai_button = QPushButton("AI ارسال به")
            self.ai_button.clicked.connect(self.ask_ai)
            self.ai_output = QTextEdit()
            self.ai_output.setReadOnly(True)

            ai_layout.addWidget(self.ai_label)
            ai_layout.addWidget(self.ai_input)
            ai_layout.addWidget(self.ai_button)
            ai_layout.addWidget(self.ai_output)

            ai_tab.setLayout(ai_layout)
            self.tabs.addTab(ai_tab, "AI")

            self.message_box = None
            
        except Exception as e:
            logger.error(f"Error creating AI tab: {e}")

    def show_loading_message(self):
        """Show loading message with error handling"""
        try:
            if self.message_box is None:
                self.message_box = QMessageBox(self)
                self.message_box.setIcon(QMessageBox.Information)
                self.message_box.setText("در حال آماده‌سازی...")
                self.message_box.setStandardButtons(QMessageBox.NoButton)
                close_button = self.message_box.addButton("بستن", QMessageBox.RejectRole)
                close_button.setStyleSheet("background-color: #f9f9f9; color: #333; font-size: 14px;")
                close_button.clicked.connect(self.hide_loading_message)
                self.message_box.show()
        except Exception as e:
            logger.error(f"Error showing loading message: {e}")

    def hide_loading_message(self):
        """Hide loading message with error handling"""
        try:
            if self.message_box:
                self.message_box.close()
                self.message_box = None
        except Exception as e:
            logger.error(f"Error hiding loading message: {e}")

    def ask_ai(self):
        """Ask AI with error handling"""
        try:
            prompt = self.ai_input.text()
            if prompt:
                if len(prompt) > 1000:
                    self._show_warning_dialog("هشدار", "متن بسیار طولانی است")
                    return
                    
                self.show_loading_message()
                self.ai_thread = SafeAskAIThread(self.ai_manager, prompt)
                self.ai_thread.finished.connect(self.on_ai_response_received)
                self.ai_thread.error_occurred.connect(self.on_ai_error)
                self.ai_thread.start()
            else:
                self.ai_output.setText("لطفاً یک متن وارد کنید.")
        except Exception as e:
            logger.error(f"Error asking AI: {e}")
            self.hide_loading_message()

    def on_ai_response_received(self, response):
        """Handle AI response with error handling"""
        try:
            self.hide_loading_message()
            self.ai_output.setText(response)
        except Exception as e:
            logger.error(f"Error handling AI response: {e}")

    def on_ai_error(self, error_message):
        """Handle AI error with error handling"""
        try:
            self.hide_loading_message()
            self._show_error_dialog("خطای AI", error_message)
        except Exception as e:
            logger.error(f"Error handling AI error: {e}")

    def create_project_management_tab(self):
        """Create project management tab with error handling"""
        try:
            project_management_tab = QWidget()
            project_management_layout = QVBoxLayout()

            self.select_project_button = QPushButton("انتخاب پروژه")
            self.select_project_button.clicked.connect(self.select_project)

            self.project_label = QLabel("مسیر پروژه انتخاب نشده است.")

            self.fix_imports_button = QPushButton("تبدیل ایمپورت‌ها")
            self.fix_imports_button.clicked.connect(self.fix_imports)

            self.suggest_structure_button = QPushButton("ایجاد ساختار پیشنهادی")
            self.suggest_structure_button.clicked.connect(self.suggest_structure)

            project_management_layout.addWidget(self.project_label)
            project_management_layout.addWidget(self.select_project_button)
            project_management_layout.addWidget(self.fix_imports_button)
            project_management_layout.addWidget(self.suggest_structure_button)

            project_management_tab.setLayout(project_management_layout)
            self.tabs.addTab(project_management_tab, "مدیریت پروژه")
            
        except Exception as e:
            logger.error(f"Error creating project management tab: {e}")

    def select_project(self):
        """Select project with error handling"""
        try:
            self.project_path = QFileDialog.getExistingDirectory(self, "انتخاب پروژه")
            if self.project_path:
                framework = detect_framework(self.project_path)
                self.project_label.setText(f"مسیر پروژه: {self.project_path} (فریم‌ورک: {framework})")
                try:
                    self.repo = git.Repo(self.project_path)
                except git.exc.InvalidGitRepositoryError:
                    self.repo = None
                    self.project_label.setText("این پروژه گیت را شناسایی نکرد.")
            else:
                self.repo = None
        except Exception as e:
            logger.error(f"Error selecting project: {e}")

    def fix_imports(self):
        """Fix imports with error handling"""
        try:
            if self.project_path:
                self.progress_bar.setVisible(True)
                self.progress_bar.setRange(0, 0)
                self.status_bar.showMessage("در حال تبدیل ایمپورت‌ها...")
                
                convert_imports_to_relative(self.project_path)
                self.project_label.setText("ایمپورت‌ها تبدیل شدند.")
                self.status_bar.showMessage("ایمپورت‌ها تبدیل شدند")
            else:
                self.project_label.setText("ابتدا یک پروژه انتخاب کنید.")
        except Exception as e:
            logger.error(f"Error fixing imports: {e}")
            self._show_error_dialog("خطا", f"خطا در تبدیل ایمپورت‌ها:\n{str(e)}")
        finally:
            self.progress_bar.setVisible(False)

    def suggest_structure(self):
        """Suggest structure with error handling"""
        try:
            if self.project_path:
                self.progress_bar.setVisible(True)
                self.progress_bar.setRange(0, 0)
                self.status_bar.showMessage("در حال ایجاد ساختار پروژه...")
                
                framework = detect_framework(self.project_path)
                create_structure(self.project_path, framework)
                categorize_files(self.project_path)
                self.project_label.setText("ساختار پروژه ایجاد شد.")
                self.status_bar.showMessage("ساختار پروژه ایجاد شد")
            else:
                self.project_label.setText("ابتدا یک پروژه انتخاب کنید.")
        except Exception as e:
            logger.error(f"Error suggesting structure: {e}")
            self._show_error_dialog("خطا", f"خطا در ایجاد ساختار پروژه:\n{str(e)}")
        finally:
            self.progress_bar.setVisible(False)

    def git_commit(self):
        """Git commit with error handling"""
        try:
            if self.repo:
                if self.repo.is_dirty():
                    self.repo.git.add(A=True)
                    self.repo.index.commit("اضافه کردن تغییرات")
                    self.project_label.setText("تغییرات با موفقیت commit شدند.")
                else:
                    self.project_label.setText("هیچ تغییراتی برای commit وجود ندارد.")
            else:
                self.project_label.setText("این پروژه گیت را شناسایی نکرد.")
        except Exception as e:
            logger.error(f"Error in git commit: {e}")
            self.project_label.setText(f"خطا در انجام commit: {str(e)}")

    def git_push(self):
        """Git push with error handling"""
        try:
            if self.repo:
                origin = self.repo.remote(name='origin')
                origin.push()
                self.project_label.setText("تغییرات با موفقیت push شدند.")
            else:
                self.project_label.setText("این پروژه گیت را شناسایی نکرد.")
        except Exception as e:
            logger.error(f"Error in git push: {e}")
            self.project_label.setText(f"خطا در انجام push: {str(e)}")

    def git_pull(self):
        """Git pull with error handling"""
        try:
            if self.repo:
                origin = self.repo.remote(name='origin')
                origin.pull()
                self.project_label.setText("تغییرات با موفقیت pull شدند.")
            else:
                self.project_label.setText("این پروژه گیت را شناسایی نکرد.")
        except Exception as e:
            logger.error(f"Error in git pull: {e}")
            self.project_label.setText(f"خطا در انجام pull: {str(e)}")

    def git_status(self):
        """Git status with error handling"""
        try:
            if self.repo:
                status = self.repo.git.status()
                self.project_label.setText(f"وضعیت گیت:\n{status}")
            else:
                self.project_label.setText("این پروژه گیت را شناسایی نکرد.")
        except Exception as e:
            logger.error(f"Error in git status: {e}")
            self.project_label.setText(f"خطا در نمایش وضعیت: {str(e)}")

    def create_settings_tab(self):
        """Create settings tab with error handling"""
        try:
            settings_tab = QWidget()
            settings_layout = QVBoxLayout()
            settings_layout.setSpacing(10)
            settings_layout.setContentsMargins(10, 10, 10, 10)

            # Title
            title_label = QLabel("تنظیمات برنامه")
            title_label.setStyleSheet("""
                font-size: 20px;
                font-weight: bold;
                color: #2c3e50;
                background-color: #ecf0f1;
                padding: 15px;
                border-radius: 8px;
                border: 2px solid #bdc3c7;
                margin-bottom: 15px;
            """)
            title_label.setAlignment(Qt.AlignCenter)
            settings_layout.addWidget(title_label)

            # AI APIs Section
            ai_group = QGroupBox("تنظیمات API های هوش مصنوعی")
            ai_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    font-size: 14px;
                    color: #2c3e50;
                    border: 2px solid #bdc3c7;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
            """)
            ai_layout = QVBoxLayout()

            # OpenAI API Key
            openai_layout = QHBoxLayout()
            openai_label = QLabel("OpenAI API Key:")
            openai_label.setMinimumWidth(120)
            self.openai_key_input = QLineEdit()
            self.openai_key_input.setEchoMode(QLineEdit.Password)
            self.openai_key_input.setText(self.settings_manager.get_ai_api_key("openai"))
            self.openai_key_input.setPlaceholderText("sk-...")
            openai_layout.addWidget(openai_label)
            openai_layout.addWidget(self.openai_key_input)
            ai_layout.addLayout(openai_layout)

            # Anthropic API Key
            anthropic_layout = QHBoxLayout()
            anthropic_label = QLabel("Anthropic API Key:")
            anthropic_label.setMinimumWidth(120)
            self.anthropic_key_input = QLineEdit()
            self.anthropic_key_input.setEchoMode(QLineEdit.Password)
            self.anthropic_key_input.setText(self.settings_manager.get_ai_api_key("anthropic"))
            self.anthropic_key_input.setPlaceholderText("sk-ant-...")
            anthropic_layout.addWidget(anthropic_label)
            anthropic_layout.addWidget(self.anthropic_key_input)
            ai_layout.addLayout(anthropic_layout)

            # Google API Key
            google_layout = QHBoxLayout()
            google_label = QLabel("Google API Key:")
            google_label.setMinimumWidth(120)
            self.google_key_input = QLineEdit()
            self.google_key_input.setEchoMode(QLineEdit.Password)
            self.google_key_input.setText(self.settings_manager.get_ai_api_key("google"))
            self.google_key_input.setPlaceholderText("AIza...")
            google_layout.addWidget(google_label)
            google_layout.addWidget(self.google_key_input)
            ai_layout.addLayout(google_layout)

            # Local AI URL
            local_layout = QHBoxLayout()
            local_label = QLabel("Local AI URL:")
            local_label.setMinimumWidth(120)
            self.local_ai_input = QLineEdit()
            self.local_ai_input.setText(self.settings_manager.get_setting("ai_apis", "local_ai_url", "http://localhost:11434"))
            self.local_ai_input.setPlaceholderText("http://localhost:11434")
            local_layout.addWidget(local_label)
            local_layout.addWidget(self.local_ai_input)
            ai_layout.addLayout(local_layout)

            ai_group.setLayout(ai_layout)
            settings_layout.addWidget(ai_group)

            # WebSocket Section
            ws_group = QGroupBox("تنظیمات WebSocket")
            ws_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    font-size: 14px;
                    color: #2c3e50;
                    border: 2px solid #bdc3c7;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
            """)
            ws_layout = QVBoxLayout()

            # Server IP
            ip_layout = QHBoxLayout()
            ip_label = QLabel("آدرس IP سرور:")
            ip_label.setMinimumWidth(120)
            self.server_ip_input = QLineEdit()
            self.server_ip_input.setText(self.settings_manager.get_setting("websocket", "server_ip", "127.0.0.1"))
            self.server_ip_input.setPlaceholderText("127.0.0.1")
            ip_layout.addWidget(ip_label)
            ip_layout.addWidget(self.server_ip_input)
            ws_layout.addLayout(ip_layout)

            # Server Port
            port_layout = QHBoxLayout()
            port_label = QLabel("پورت سرور:")
            port_label.setMinimumWidth(120)
            self.server_port_input = QSpinBox()
            self.server_port_input.setRange(1, 65535)
            self.server_port_input.setValue(self.settings_manager.get_setting("websocket", "server_port", 8765))
            port_layout.addWidget(port_label)
            port_layout.addWidget(self.server_port_input)
            ws_layout.addLayout(port_layout)

            ws_group.setLayout(ws_layout)
            settings_layout.addWidget(ws_group)

            # Test Connection Button
            test_button = QPushButton("تست اتصال WebSocket")
            test_button.setStyleSheet("""
                QPushButton {
                    font-size: 12px;
                    font-weight: bold;
                    color: white;
                    background-color: #3498db;
                    padding: 8px 16px;
                    border-radius: 4px;
                    border: 2px solid #2980b9;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #1c5980;
                }
            """)
            test_button.clicked.connect(self.test_websocket_connection)
            settings_layout.addWidget(test_button)

            # General Settings Section
            general_group = QGroupBox("تنظیمات عمومی")
            general_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    font-size: 14px;
                    color: #2c3e50;
                    border: 2px solid #bdc3c7;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
            """)
            general_layout = QVBoxLayout()

            # Auto Save
            self.auto_save_checkbox = QCheckBox("ذخیره خودکار فایل‌ها")
            self.auto_save_checkbox.setChecked(self.settings_manager.get_setting("general", "auto_save", True))
            general_layout.addWidget(self.auto_save_checkbox)

            # Auto Complete
            self.auto_complete_checkbox = QCheckBox("تکمیل خودکار کد")
            self.auto_complete_checkbox.setChecked(self.settings_manager.get_setting("general", "auto_complete", True))
            general_layout.addWidget(self.auto_complete_checkbox)

            general_group.setLayout(general_layout)
            settings_layout.addWidget(general_group)

            # Buttons
            button_layout = QHBoxLayout()
            
            save_button = QPushButton("ذخیره تنظیمات")
            save_button.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: bold;
                    color: white;
                    background-color: #27ae60;
                    padding: 10px 20px;
                    border-radius: 5px;
                    border: 2px solid #229954;
                }
                QPushButton:hover {
                    background-color: #229954;
                }
                QPushButton:pressed {
                    background-color: #1e8449;
                }
            """)
            save_button.clicked.connect(self.save_settings)
            
            reset_button = QPushButton("بازنشانی به پیش‌فرض")
            reset_button.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: bold;
                    color: white;
                    background-color: #e74c3c;
                    padding: 10px 20px;
                    border-radius: 5px;
                    border: 2px solid #c0392b;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
                QPushButton:pressed {
                    background-color: #a93226;
                }
            """)
            reset_button.clicked.connect(self.reset_settings)
            
            button_layout.addWidget(save_button)
            button_layout.addWidget(reset_button)
            settings_layout.addLayout(button_layout)

            settings_tab.setLayout(settings_layout)
            self.tabs.addTab(settings_tab, "تنظیمات")
            
            # Load current settings to UI
            self.load_settings_to_ui()
            
        except Exception as e:
            logger.error(f"Error creating settings tab: {e}")

    def save_settings(self):
        """Save all settings with error handling"""
        try:
            # Save AI API keys
            self.settings_manager.set_ai_api_key("openai", self.openai_key_input.text())
            self.settings_manager.set_ai_api_key("anthropic", self.anthropic_key_input.text())
            self.settings_manager.set_ai_api_key("google", self.google_key_input.text())
            self.settings_manager.set_setting("ai_apis", "local_ai_url", self.local_ai_input.text())
            
            # Save WebSocket settings
            websocket_config = {
                "server_ip": self.server_ip_input.text(),
                "server_port": self.server_port_input.value(),
                "client_url": f"ws://{self.server_ip_input.text()}:{self.server_port_input.value()}"
            }
            self.settings_manager.set_websocket_config(websocket_config)
            
            # Save general settings
            self.settings_manager.set_setting("general", "auto_save", self.auto_save_checkbox.isChecked())
            self.settings_manager.set_setting("general", "auto_complete", self.auto_complete_checkbox.isChecked())
            
            # Reconnect WebSocket with new settings
            self.reconnect_websocket()
            
            self._show_success_dialog("موفق", "تنظیمات با موفقیت ذخیره شد.")
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            self._show_error_dialog("خطا", f"خطا در ذخیره تنظیمات: {str(e)}")

    def reconnect_websocket(self):
        """Reconnect WebSocket with new settings"""
        try:
            # Close existing connection
            if hasattr(self, 'collab_client'):
                self.collab_client.close()
            
            # Get new WebSocket config
            websocket_config = self.settings_manager.get_websocket_config()
            client_url = websocket_config.get("client_url", "ws://127.0.0.1:8765")
            
            # Reconnect with new URL
            self.collab_client.connect(client_url)
            
            logger.info(f"WebSocket reconnected to: {client_url}")
            
        except Exception as e:
            logger.error(f"Error reconnecting WebSocket: {e}")
            self._show_warning_dialog("هشدار", f"خطا در اتصال مجدد WebSocket: {str(e)}")

    def reset_settings(self):
        """Reset settings to defaults with error handling"""
        try:
            reply = QMessageBox.question(
                self, "تأیید بازنشانی", 
                "آیا مطمئن هستید که می‌خواهید تمام تنظیمات را به مقادیر پیش‌فرض بازنشانی کنید؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.settings_manager.reset_to_defaults()
                self.load_settings_to_ui()
                self._show_success_dialog("موفق", "تنظیمات به مقادیر پیش‌فرض بازنشانی شد.")
                
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            self._show_error_dialog("خطا", f"خطا در بازنشانی تنظیمات: {str(e)}")

    def load_settings_to_ui(self):
        """Load settings from manager to UI with error handling"""
        try:
            # Load AI API keys
            self.openai_key_input.setText(self.settings_manager.get_ai_api_key("openai"))
            self.anthropic_key_input.setText(self.settings_manager.get_ai_api_key("anthropic"))
            self.google_key_input.setText(self.settings_manager.get_ai_api_key("google"))
            self.local_ai_input.setText(self.settings_manager.get_setting("ai_apis", "local_ai_url", "http://localhost:11434"))
            
            # Load WebSocket settings
            self.server_ip_input.setText(self.settings_manager.get_setting("websocket", "server_ip", "127.0.0.1"))
            self.server_port_input.setValue(self.settings_manager.get_setting("websocket", "server_port", 8765))
            
            # Load general settings
            self.auto_save_checkbox.setChecked(self.settings_manager.get_setting("general", "auto_save", True))
            self.auto_complete_checkbox.setChecked(self.settings_manager.get_setting("general", "auto_complete", True))
            
        except Exception as e:
            logger.error(f"Error loading settings to UI: {e}")

    def create_vision_tab(self):
        """Create vision tab with error handling"""
        try:
            vision_tab = QWidget()
            vision_layout = QVBoxLayout()
            vision_layout.setSpacing(2)
            vision_layout.setContentsMargins(2, 2, 2, 2)

            # Camera selection
            self.vision_manager = VisionManager()
            self.camera_combo = QComboBox()
            self.camera_combo.setMaximumHeight(25)
            for i in self.vision_manager.available_cameras:
                self.camera_combo.addItem(f"دوربین {i}")
            
            if not self.vision_manager.available_cameras:
                self.camera_combo.addItem("دوربینی یافت نشد")
                self.camera_combo.setEnabled(False)
            
            # Camera view
            self.camera_label = QLabel()
            self.camera_label.setMinimumSize(320, 240)
            self.camera_label.setAlignment(Qt.AlignCenter)
            self.camera_label.setStyleSheet("border: 1px solid #ccc; border-radius: 3px;")
            self.camera_label.setText("دوربین انتخاب نشده است")

            # Text input area
            self.vision_text = QTextEdit()
            self.vision_text.setPlaceholderText("متن تایپ شده با حرکات دست...")
            self.vision_text.setReadOnly(True)
            self.vision_text.setMaximumHeight(100)

            # Control buttons
            button_layout = QHBoxLayout()
            button_layout.setSpacing(2)
            
            self.start_vision_button = QPushButton("شروع")
            self.start_vision_button.setMaximumWidth(80)
            self.start_vision_button.clicked.connect(self.start_vision)
            
            self.stop_vision_button = QPushButton("توقف")
            self.stop_vision_button.setMaximumWidth(80)
            self.stop_vision_button.clicked.connect(self.stop_vision)
            
            self.save_text_button = QPushButton("ذخیره")
            self.save_text_button.setMaximumWidth(80)
            self.save_text_button.clicked.connect(self.save_vision_text)
            
            self.stop_vision_button.setEnabled(False)

            button_layout.addWidget(self.start_vision_button)
            button_layout.addWidget(self.stop_vision_button)
            button_layout.addWidget(self.save_text_button)

            # Add widgets to layout
            vision_layout.addWidget(QLabel("دوربین:"))
            vision_layout.addWidget(self.camera_combo)
            vision_layout.addWidget(self.camera_label)
            vision_layout.addWidget(QLabel("متن:"))
            vision_layout.addWidget(self.vision_text)
            vision_layout.addLayout(button_layout)

            vision_tab.setLayout(vision_layout)
            self.tabs.addTab(vision_tab, "تایپ با حرکات دست")
            
        except Exception as e:
            logger.error(f"Error creating vision tab: {e}")

    def start_vision(self):
        """Start vision with error handling"""
        try:
            if not self.vision_manager.available_cameras:
                self._show_warning_dialog("هشدار", "دوربینی در سیستم یافت نشد.")
                return

            camera_index = self.camera_combo.currentIndex()
            if self.vision_manager.start_vision(camera_index):
                # Connect signals
                self.vision_manager.vision_thread.frame_ready.connect(self.update_vision_frame)
                self.vision_manager.vision_thread.key_pressed.connect(self.handle_vision_key_press)
                self.vision_manager.vision_thread.error_occurred.connect(self.handle_vision_error)
                
                self.start_vision_button.setEnabled(False)
                self.stop_vision_button.setEnabled(True)
        except Exception as e:
            logger.error(f"Error starting vision: {e}")
            self._show_error_dialog("خطا", f"خطا در شروع دوربین: {str(e)}")

    def handle_vision_error(self, error_message):
        """Handle vision error with error handling"""
        try:
            self._show_error_dialog("خطای دوربین", error_message)
            self.stop_vision()
        except Exception as e:
            logger.error(f"Error handling vision error: {e}")

    def stop_vision(self):
        """Stop vision with error handling"""
        try:
            if hasattr(self, 'vision_manager'):
                self.vision_manager.stop_vision()
                self.camera_label.clear()
                self.camera_label.setText("دوربین متوقف شد")
                self.start_vision_button.setEnabled(True)
                self.stop_vision_button.setEnabled(False)
        except Exception as e:
            logger.error(f"Error stopping vision: {e}")
            self._show_error_dialog("خطا", f"خطا در توقف دوربین: {str(e)}")

    def update_vision_frame(self, image):
        """Update vision frame with error handling"""
        try:
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                scaled_pixmap = pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio)
                self.camera_label.setPixmap(scaled_pixmap)
        except Exception as e:
            logger.error(f"Error updating vision frame: {e}")
            self.handle_vision_error("خطا در به‌روزرسانی تصویر دوربین")

    def handle_vision_key_press(self, key):
        """Handle vision key press with error handling"""
        try:
            if self.text_processed:
                return
                
            current_text = self.vision_text.toPlainText()
            if key == 'backspace':
                if current_text:
                    self.vision_text.setPlainText(current_text[:-1])
                    self.text_processed = True
            elif key == ' ':
                if not current_text.endswith(' '):
                    self.vision_text.setPlainText(current_text + ' ')
                    self.text_processed = True
            elif key == '\n':
                self.vision_text.setPlainText(current_text + '\n')
                self.text_processed = True
            else:
                self.vision_text.setPlainText(current_text + key)
                self.text_processed = True
        except Exception as e:
            logger.error(f"Error handling vision key press: {e}")
        finally:
            self.text_processed = False

    def save_vision_text(self):
        """Save vision text with error handling"""
        try:
            text = self.vision_text.toPlainText()
            if text:
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "ذخیره متن", "", "Text Files (*.txt);;All Files (*)")
                if file_path:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(text)
                    self._show_success_dialog("موفق", "متن با موفقیت ذخیره شد.")
            else:
                self._show_warning_dialog("هشدار", "هیچ متنی برای ذخیره وجود ندارد.")
        except Exception as e:
            logger.error(f"Error saving vision text: {e}")
            self._show_error_dialog("خطا", f"خطا در ذخیره فایل: {str(e)}")

    def test_websocket_connection(self):
        """Test WebSocket connection with error handling"""
        try:
            # Get current WebSocket config from UI
            server_ip = self.server_ip_input.text()
            server_port = self.server_port_input.value()
            client_url = f"ws://{server_ip}:{server_port}"
            
            # Temporarily connect to test
            temp_socket = QWebSocket()
            temp_socket.connected.connect(lambda: self.on_test_connected(temp_socket))
            temp_socket.error.connect(lambda error: self.on_test_error(temp_socket, error))
            
            # Set a timeout for the test
            QTimer.singleShot(5000, lambda: self.on_test_timeout(temp_socket))
            
            temp_socket.open(QUrl(client_url))
            
        except Exception as e:
            logger.error(f"Error testing WebSocket connection: {e}")
            self._show_error_dialog("خطا", f"خطا در تست اتصال WebSocket: {str(e)}")

    def on_test_connected(self, temp_socket):
        """Handle successful test connection"""
        try:
            temp_socket.close()
            self._show_success_dialog("موفق", "اتصال WebSocket با موفقیت برقرار شد.")
        except Exception as e:
            logger.error(f"Error in test connection success: {e}")

    def on_test_error(self, temp_socket, error):
        """Handle test connection error"""
        try:
            temp_socket.close()
            self._show_error_dialog("خطا", f"خطا در اتصال WebSocket: {error}")
        except Exception as e:
            logger.error(f"Error in test connection error: {e}")

    def on_test_timeout(self, temp_socket):
        """Handle test connection timeout"""
        try:
            if temp_socket.state() == QWebSocket.ConnectingState:
                temp_socket.close()
                self._show_warning_dialog("هشدار", "اتصال WebSocket با تایم‌اوت مواجه شد.")
        except Exception as e:
            logger.error(f"Error in test connection timeout: {e}")


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)

        # Set up Persian fonts for the entire application
        persian_font_family = setup_persian_fonts(app)
    
        window = SafeMainWindow()
        window.show()
        
        logger.info("Application started successfully")
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.critical(f"Critical error starting application: {e}")
        print(f"Critical error: {e}")
        sys.exit(1)

# Backward compatibility alias
MainWindow = SafeMainWindow