import os

def detect_framework(project_path):
    """
    شناسایی فریم‌ورک پروژه بر اساس فایل‌های موجود در مسیر پروژه
    """
    # بررسی وجود فایل‌های مربوط به Kivy
    if any(file.endswith('.kv') for file in os.listdir(project_path)):
        return "Kivy"
    # بررسی وجود فایل app.py برای Flask
    elif 'app.py' in os.listdir(project_path):
        return "Flask"
    # بررسی وجود فایل‌های .ui برای PyQt5
    elif any(file.endswith('.ui') for file in os.listdir(project_path)):
        return "PyQt5"
    # بررسی وجود pygame در فایل‌های پایتون برای Pygame
    elif any(file.endswith('.py') and 'pygame' in open(os.path.join(project_path, file)).read() 
             for file in os.listdir(project_path)):
        return "Pygame"
    # اگر هیچ فریم‌ورکی شناسایی نشد
    return "Unknown"

