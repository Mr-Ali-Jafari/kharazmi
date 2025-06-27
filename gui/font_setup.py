"""
اسکریپت راه‌اندازی فونت فارسی برای CodePrime
این اسکریپت به کاربران کمک می‌کند تا در صورت نبود فونت‌های فارسی، آن‌ها را نصب کنند.
بهینه‌شده با مدیریت خطا و جلوگیری از کرش.
"""

import os
import sys
import platform
import subprocess
import urllib.request
import zipfile
import tempfile
import shutil
import time
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from contextlib import contextmanager

# تنظیمات لاگ‌گیری
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('font_setup.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FontSetupError(Exception):
    """
    استثنای اختصاصی برای خطاهای راه‌اندازی فونت
    """
    pass

class SafeFontSetup:
    """
    راه‌اندازی امن فونت با مدیریت خطا
    """
    
    def __init__(self):
        # لیست فونت‌های فارسی
        self.persian_fonts = [
            'Vazirmatn',
            'B Nazanin', 
            'B Titr',
            'B Yekan',
            'B Mitra',
            'B Lotus',
            'B Traffic'
        ]
        self.download_timeout = 60  # زمان انتظار دانلود
        self.max_retries = 3
        
    def check_font_availability(self) -> Tuple[List[str], List[str]]:
        """
        بررسی وجود فونت‌های فارسی در سیستم با مدیریت خطا
        """
        try:
            available_fonts = []
            missing_fonts = []
            
            system = platform.system()
            
            if system == "Windows":
                available_fonts, missing_fonts = self._check_windows_fonts()
            elif system == "Darwin":  # macOS
                available_fonts, missing_fonts = self._check_macos_fonts()
            else:  # Linux
                available_fonts, missing_fonts = self._check_linux_fonts()
            
            logger.info(f"Font check completed. Available: {len(available_fonts)}, Missing: {len(missing_fonts)}")
            return available_fonts, missing_fonts
            
        except Exception as e:
            logger.error(f"Error checking font availability: {e}")
            return [], self.persian_fonts.copy()

    def _check_windows_fonts(self) -> Tuple[List[str], List[str]]:
        """
        بررسی فونت‌ها در ویندوز
        """
        try:
            import winreg
            available_fonts = []
            missing_fonts = []
            
            font_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
            
            for font in self.persian_fonts:
                try:
                    winreg.QueryValueEx(font_key, font)[0]
                    available_fonts.append(font)
                except FileNotFoundError:
                    missing_fonts.append(font)
                except Exception as e:
                    logger.warning(f"Error checking font {font}: {e}")
                    missing_fonts.append(font)
            
            winreg.CloseKey(font_key)
            return available_fonts, missing_fonts
            
        except Exception as e:
            logger.error(f"Error checking Windows fonts: {e}")
            return [], self.persian_fonts.copy()

    def _check_macos_fonts(self) -> Tuple[List[str], List[str]]:
        """
        بررسی فونت‌ها در مک‌اواس
        """
        try:
            available_fonts = []
            missing_fonts = []
            
            font_paths = [
                "/System/Library/Fonts",
                "/Library/Fonts",
                os.path.expanduser("~/Library/Fonts")
            ]
            
            for font in self.persian_fonts:
                font_found = False
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        for file in os.listdir(font_path):
                            if font.lower() in file.lower() and file.endswith(('.ttf', '.otf')):
                                available_fonts.append(font)
                                font_found = True
                                break
                    if font_found:
                        break
                
                if not font_found:
                    missing_fonts.append(font)
            
            return available_fonts, missing_fonts
            
        except Exception as e:
            logger.error(f"Error checking macOS fonts: {e}")
            return [], self.persian_fonts.copy()

    def _check_linux_fonts(self) -> Tuple[List[str], List[str]]:
        """
        بررسی فونت‌ها در لینوکس
        """
        try:
            available_fonts = []
            missing_fonts = []
            
            # تلاش برای استفاده از fc-list
            try:
                result = subprocess.run(['fc-list', '--format=%{family}\n'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    installed_fonts = result.stdout.lower()
                    for font in self.persian_fonts:
                        if font.lower() in installed_fonts:
                            available_fonts.append(font)
                        else:
                            missing_fonts.append(font)
                else:
                    # اگر fc-list نبود، بررسی دایرکتوری
                    available_fonts, missing_fonts = self._check_linux_fonts_directories()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                available_fonts, missing_fonts = self._check_linux_fonts_directories()
            
            return available_fonts, missing_fonts
            
        except Exception as e:
            logger.error(f"Error checking Linux fonts: {e}")
            return [], self.persian_fonts.copy()

    def _check_linux_fonts_directories(self) -> Tuple[List[str], List[str]]:
        """
        بررسی دایرکتوری‌های فونت لینوکس
        """
        try:
            available_fonts = []
            missing_fonts = []
            
            font_paths = [
                "/usr/share/fonts",
                "/usr/local/share/fonts",
                os.path.expanduser("~/.local/share/fonts"),
                os.path.expanduser("~/.fonts")
            ]
            
            for font in self.persian_fonts:
                font_found = False
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        for root, dirs, files in os.walk(font_path):
                            for file in files:
                                if font.lower() in file.lower() and file.endswith(('.ttf', '.otf')):
                                    available_fonts.append(font)
                                    font_found = True
                                    break
                            if font_found:
                                break
                    if font_found:
                        break
                
                if not font_found:
                    missing_fonts.append(font)
            
            return available_fonts, missing_fonts
            
        except Exception as e:
            logger.error(f"Error checking Linux font directories: {e}")
            return [], self.persian_fonts.copy()

    def get_font_installation_path(self) -> str:
        """
        دریافت مسیر نصب فونت مناسب سیستم عامل با مدیریت خطا
        """
        try:
            system = platform.system()
            
            if system == "Windows":
                font_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
            elif system == "Darwin":  # macOS
                font_path = os.path.expanduser("~/Library/Fonts")
            else:  # Linux
                font_path = os.path.expanduser("~/.local/share/fonts")
            
            logger.info(f"Font installation path: {font_path}")
            return font_path
            
        except Exception as e:
            logger.error(f"Error getting font installation path: {e}")
            raise FontSetupError(f"Could not determine font installation path: {e}")

    def download_vazirmatn_font(self) -> List[str]:
        """
        دانلود فونت وزیرمتن از گیت‌هاب با مدیریت خطا و تلاش مجدد
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Downloading Vazirmatn font (attempt {attempt + 1}/{self.max_retries})")
                font_url = "https://github.com/rastikerdar/vazirmatn/releases/download/v33.003/vazirmatn-v33.003.zip"
                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_path = os.path.join(temp_dir, "vazirmatn.zip")
                    self._download_file_with_progress(font_url, zip_path)
                    font_files = self._extract_font_files(zip_path, temp_dir)
                    if font_files:
                        logger.info(f"Successfully downloaded {len(font_files)} font files")
                        return font_files
                    else:
                        logger.warning("No font files found in downloaded archive")
            except Exception as e:
                logger.error(f"Download attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise FontSetupError(f"Failed to download font after {self.max_retries} attempts: {e}")
        return []

    def _download_file_with_progress(self, url: str, file_path: str):
        """
        دانلود فایل با نمایش پیشرفت و مدیریت زمان انتظار
        """
        try:
            print(f"Downloading from {url}...")
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')]
            with opener.open(url, timeout=self.download_timeout) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\rDownload progress: {progress:.1f}%", end='', flush=True)
                print()
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise FontSetupError(f"Download failed: {e}")

    def _extract_font_files(self, zip_path: str, temp_dir: str) -> List[str]:
        """
        استخراج فایل‌های فونت از زیپ با مدیریت خطا
        """
        try:
            font_files = []
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                total_size = sum(info.file_size for info in zip_ref.infolist())
                if total_size > 100 * 1024 * 1024:
                    raise FontSetupError("Archive too large, possible zip bomb")
                zip_ref.extractall(temp_dir)
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith(('.ttf', '.otf')):
                        font_files.append(os.path.join(root, file))
            return font_files
        except zipfile.BadZipFile:
            raise FontSetupError("Invalid zip file")
        except Exception as e:
            logger.error(f"Error extracting font files: {e}")
            raise FontSetupError(f"Extraction failed: {e}")

    def install_fonts(self, font_files: List[str]) -> int:
        """
        نصب فایل‌های فونت در سیستم با مدیریت خطا
        """
        try:
            font_path = self.get_font_installation_path()
            if not os.path.exists(font_path):
                os.makedirs(font_path, exist_ok=True)
                logger.info(f"Created font directory: {font_path}")
            installed_count = 0
            for font_file in font_files:
                try:
                    font_name = os.path.basename(font_file)
                    dest_path = os.path.join(font_path, font_name)
                    if os.path.exists(dest_path):
                        backup_path = dest_path + f".backup.{int(time.time())}"
                        shutil.copy2(dest_path, backup_path)
                        logger.info(f"Created backup: {backup_path}")
                    shutil.copy2(font_file, dest_path)
                    print(f"Installed: {font_name}")
                    installed_count += 1
                except Exception as e:
                    logger.error(f"Error installing {font_file}: {e}")
                    print(f"Failed to install: {os.path.basename(font_file)}")
            return installed_count
        except Exception as e:
            logger.error(f"Error installing fonts: {e}")
            raise FontSetupError(f"Font installation failed: {e}")

    def refresh_font_cache(self):
        """
        به‌روزرسانی کش فونت سیستم با مدیریت خطا
        """
        try:
            system = platform.system()
            if system == "Linux":
                try:
                    subprocess.run(["fc-cache", "-f", "-v"], check=True, timeout=30)
                    print("Font cache refreshed.")
                except subprocess.TimeoutExpired:
                    logger.warning("Font cache refresh timed out")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Font cache refresh failed: {e}")
            elif system == "Darwin":  # macOS
                try:
                    subprocess.run(["sudo", "fc-cache", "-f", "-v"], check=True, timeout=30)
                    print("Font cache refreshed.")
                except subprocess.TimeoutExpired:
                    logger.warning("Font cache refresh timed out")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Font cache refresh failed: {e}")
            # ویندوز نیاز به به‌روزرسانی کش ندارد
        except Exception as e:
            logger.error(f"Error refreshing font cache: {e}")

    def validate_installation(self) -> bool:
        """
        اعتبارسنجی نصب صحیح فونت‌ها
        """
        try:
            available_fonts, _ = self.check_font_availability()
            return len(available_fonts) > 0
        except Exception as e:
            logger.error(f"Error validating installation: {e}")
            return False

    def cleanup_backups(self, max_age_hours: int = 24):
        """
        پاک‌سازی فایل‌های پشتیبان قدیمی
        """
        try:
            font_path = self.get_font_installation_path()
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            for file in os.listdir(font_path):
                if file.endswith('.backup.'):
                    file_path = os.path.join(font_path, file)
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        os.remove(file_path)
                        logger.info(f"Cleaned up old backup: {file}")
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")

@contextmanager
def safe_operation(operation_name: str):
    """
    مدیریت امن عملیات‌ها با ثبت خطا
    """
    try:
        yield
    except Exception as e:
        logger.error(f"Error in {operation_name}: {e}")
        raise

def main():
    """
    تابع اصلی برای راه‌اندازی فونت فارسی با مدیریت خطا
    """
    print("=== Persian Font Setup for CodePrime ===\n")
    setup = SafeFontSetup()
    try:
        with safe_operation("font availability check"):
            available, missing = setup.check_font_availability()
            print(f"Available Persian fonts: {', '.join(available) if available else 'None'}")
            print(f"Missing Persian fonts: {', '.join(missing) if missing else 'None'}")
        if not available:
            print("\nNo Persian fonts found. Would you like to install Vazirmatn font?")
            response = input("Install Vazirmatn font? (y/n): ").lower().strip()
            if response in ['y', 'yes']:
                print("\nInstalling Vazirmatn font...")
                with safe_operation("font download and installation"):
                    font_files = setup.download_vazirmatn_font()
                    if font_files:
                        installed = setup.install_fonts(font_files)
                        print(f"\nSuccessfully installed {installed} font files.")
                        setup.refresh_font_cache()
                        if setup.validate_installation():
                            print("\nFont installation complete! Please restart CodePrime for changes to take effect.")
                        else:
                            print("\nFont installation completed but validation failed. Please check manually.")
                    else:
                        print("\nFailed to download fonts. Please install Persian fonts manually.")
            else:
                print("\nFont installation skipped. CodePrime will use fallback fonts.")
        else:
            print("\nPersian fonts are already available. No installation needed.")
        setup.cleanup_backups()
    except FontSetupError as e:
        print(f"\n❌ Font setup error: {e}")
        logger.error(f"Font setup failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    print("\n=== Setup Complete ===")

if __name__ == "__main__":
    main() 