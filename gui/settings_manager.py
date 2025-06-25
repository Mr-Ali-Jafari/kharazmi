import json
import os
from typing import Dict, Any, Optional

class SettingsManager:
    """مدیریت تنظیمات برنامه شامل API های AI و آدرس‌های WebSocket"""
    
    def __init__(self, settings_file: str = "settings.json"):
        self.settings_file = settings_file
        self.default_settings = {
            "ai_apis": {
                "openai_api_key": "",
                "openai_base_url": "https://api.openai.com/v1",
                "anthropic_api_key": "",
                "google_api_key": "",
                "local_ai_url": "http://localhost:11434"
            },
            "websocket": {
                "server_ip": "127.0.0.1",
                "server_port": 8765,
                "client_url": "ws://127.0.0.1:8765"
            },
            "general": {
                "language": "fa",
                "theme": "light",
                "auto_save": True,
                "auto_complete": True
            }
        }
        self.settings = self.load_settings()
    
    def load_settings(self) -> Dict[str, Any]:
        """بارگذاری تنظیمات از فایل"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # ادغام با تنظیمات پیش‌فرض
                    return self._merge_settings(self.default_settings, loaded_settings)
            else:
                # ایجاد فایل تنظیمات با مقادیر پیش‌فرض
                self.save_settings(self.default_settings)
                return self.default_settings.copy()
        except Exception as e:
            print(f"خطا در بارگذاری تنظیمات: {e}")
            return self.default_settings.copy()
    
    def save_settings(self, settings: Optional[Dict[str, Any]] = None) -> bool:
        """ذخیره تنظیمات در فایل"""
        try:
            if settings is None:
                settings = self.settings
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"خطا در ذخیره تنظیمات: {e}")
            return False
    
    def _merge_settings(self, default: Dict[str, Any], loaded: Dict[str, Any]) -> Dict[str, Any]:
        """ادغام تنظیمات بارگذاری شده با تنظیمات پیش‌فرض"""
        merged = default.copy()
        for key, value in loaded.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_settings(merged[key], value)
            else:
                merged[key] = value
        return merged
    
    def get_ai_api_key(self, provider: str) -> str:
        """دریافت کلید API برای ارائه‌دهنده مشخص"""
        return self.settings.get("ai_apis", {}).get(f"{provider}_api_key", "")
    
    def set_ai_api_key(self, provider: str, api_key: str) -> bool:
        """تنظیم کلید API برای ارائه‌دهنده مشخص"""
        if "ai_apis" not in self.settings:
            self.settings["ai_apis"] = {}
        self.settings["ai_apis"][f"{provider}_api_key"] = api_key
        return self.save_settings()
    
    def get_websocket_config(self) -> Dict[str, Any]:
        """دریافت تنظیمات WebSocket"""
        return self.settings.get("websocket", {})
    
    def set_websocket_config(self, config: Dict[str, Any]) -> bool:
        """تنظیم پیکربندی WebSocket"""
        self.settings["websocket"] = config
        return self.save_settings()
    
    def get_setting(self, category: str, key: str, default: Any = None) -> Any:
        """دریافت یک تنظیم خاص"""
        return self.settings.get(category, {}).get(key, default)
    
    def set_setting(self, category: str, key: str, value: Any) -> bool:
        """تنظیم یک مقدار خاص"""
        if category not in self.settings:
            self.settings[category] = {}
        self.settings[category][key] = value
        return self.save_settings()
    
    def reset_to_defaults(self) -> bool:
        """بازنشانی تنظیمات به مقادیر پیش‌فرض"""
        self.settings = self.default_settings.copy()
        return self.save_settings()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """دریافت تمام تنظیمات"""
        return self.settings.copy() 