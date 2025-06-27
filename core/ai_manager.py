import requests

class AIManager:
    """
    مدیریت ارتباط با هوش مصنوعی و دریافت پاسخ از API
    """
    def __init__(self, api_key: str, base_url: str = "https://openai.jabirproject.org/v1"):
        """
        مقداردهی اولیه کلاس با کلید API و آدرس پایه
        """
        self.api_key = api_key
        self.base_url = base_url
        self.system_message = """این هوش مصنوعی جهت استفاده در جشنواره خوارزمی طراحی شده است.
این پروژه توسط علی جعفری و با استفاده از پروژه Jabir پیاده‌سازی شده است.
لطفا سوال خود را مطرح کنید."""

    def get_ai_response(self, prompt: str, model: str = "jabir-400b") -> str:
        """
        ارسال درخواست به API و دریافت پاسخ هوش مصنوعی
        """
        try:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": prompt}
                ]
            }
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                ai_response = result["choices"][0]["message"]["content"].strip()
                # بازگرداندن پیام سیستم و پاسخ هوش مصنوعی
                return f"{self.system_message}\n\nپاسخ:\n{ai_response}"
            else:
                return f"خطا در ارتباط با API: کد وضعیت {response.status_code}"
        except Exception as e:
            return f"خطا در ارتباط با API: {str(e)}"