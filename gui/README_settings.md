# راهنمای تنظیمات برنامه

## تب تنظیمات

تب تنظیمات به شما امکان مدیریت API های هوش مصنوعی و آدرس‌های WebSocket را می‌دهد.

### تنظیمات API های هوش مصنوعی

#### OpenAI API
- **API Key**: کلید API از OpenAI را وارد کنید
- فرمت: `sk-...`
- برای دریافت کلید به [OpenAI Platform](https://platform.openai.com/api-keys) مراجعه کنید

#### Anthropic API
- **API Key**: کلید API از Anthropic را وارد کنید
- فرمت: `sk-ant-...`
- برای دریافت کلید به [Anthropic Console](https://console.anthropic.com/) مراجعه کنید

#### Google API
- **API Key**: کلید API از Google را وارد کنید
- فرمت: `AIza...`
- برای دریافت کلید به [Google AI Studio](https://aistudio.google.com/) مراجعه کنید

#### Local AI URL
- آدرس سرور AI محلی (مثل Ollama)
- پیش‌فرض: `http://localhost:11434`

### تنظیمات WebSocket

#### آدرس IP سرور
- آدرس IP سرور WebSocket
- پیش‌فرض: `127.0.0.1`

#### پورت سرور
- پورت سرور WebSocket
- پیش‌فرض: `8765`

#### تست اتصال
- دکمه "تست اتصال WebSocket" برای بررسی اتصال به سرور

### تنظیمات عمومی

#### ذخیره خودکار فایل‌ها
- فعال/غیرفعال کردن ذخیره خودکار فایل‌ها

#### تکمیل خودکار کد
- فعال/غیرفعال کردن پیشنهادات هوشمند کد

### دکمه‌های عملیات

#### ذخیره تنظیمات
- ذخیره تمام تنظیمات در فایل `settings.json`
- اتصال مجدد WebSocket با تنظیمات جدید

#### بازنشانی به پیش‌فرض
- بازنشانی تمام تنظیمات به مقادیر پیش‌فرض
- نیاز به تأیید کاربر

## فایل تنظیمات

تنظیمات در فایل `settings.json` ذخیره می‌شوند:

```json
{
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
    "auto_save": true,
    "auto_complete": true
  }
}
```

## نکات مهم

1. **امنیت**: کلیدهای API به صورت رمزگذاری شده در فایل ذخیره می‌شوند
2. **اتصال مجدد**: پس از تغییر تنظیمات WebSocket، اتصال به طور خودکار مجدداً برقرار می‌شود
3. **پشتیبان‌گیری**: فایل `settings.json` را در جای امنی نگهداری کنید
4. **خطاها**: در صورت بروز خطا، پیام‌های مناسب نمایش داده می‌شود 