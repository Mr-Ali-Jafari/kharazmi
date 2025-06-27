import os
import shutil

def suggest_structure(framework):
    """
    پیشنهاد ساختار پوشه‌ها بر اساس فریم‌ورک انتخابی
    """
    structures = {
        "Kivy": ["views/", "controllers/", "models/"],
        "Pygame": ["assets/", "sprites/", "events/"],
        "PyQt5": ["ui/", "controllers/", "models/"],
        "Flask": ["routes/", "templates/", "models/"],
        "Django": ["apps/", "templates/", "static/", "models/"],
        "FastAPI": ["routes/", "templates/", "models/"],
        "Tkinter": ["views/", "controllers/", "models/"],
        "Bottle": ["routes/", "views/", "templates/"],
        "CherryPy": ["controllers/", "views/", "models/"],
    }
    return structures.get(framework, [])

def create_structure(project_path, framework):
    """
    ایجاد ساختار پوشه‌ای پیشنهادی بر اساس فریم‌ورک
    """
    structure = suggest_structure(framework)
    for folder in structure:
        path = os.path.join(project_path, folder)
        os.makedirs(path, exist_ok=True)

def categorize_files(project_path):
    """
    دسته‌بندی و انتقال فایل‌ها به پوشه‌های مناسب بر اساس نوع و نام فایل
    """
    categories = {
        "views": [".kv", ".html", ".ui", ".xml", ".tpl", ".xaml"],  
        "controllers": ["_controller.py", "controller.py", "views.py", "_views.py"], 
        "models": ["_model.py", "model.py", "models.py"], 
        "assets": [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".svg"],  
        "sprites": ["_sprite.py", "sprite.py", "_image.py", "image.py"], 
        "events": ["_event.py", "event.py", "_signals.py", "signals.py"], 
        "routes": ["app.py", "routes.py", "_routes.py", "urls.py"],
        "templates": [".html", ".jinja2", ".tpl", ".htm"],  
        "static": [".css", ".js", ".json"], 
        "tests": ["test_", "tests_"], 
        "migrations": ["migrations/"],  
        "docs": [".md", ".rst"], 
    }
    
    for root, _, files in os.walk(project_path):
        for file in files:
            src_path = os.path.join(root, file)
            # فقط فایل‌های موجود در ریشه پروژه بررسی شوند
            if root != project_path:  
                continue
            moved = False
            for folder, extensions in categories.items():
                # اگر پسوند یا نام فایل با قوانین دسته‌بندی مطابقت داشت، انتقال به پوشه مناسب
                if any(file.endswith(ext) for ext in extensions) or any(name in file for name in extensions):
                    dest_folder = os.path.join(project_path, folder)
                    os.makedirs(dest_folder, exist_ok=True)  
                    shutil.move(src_path, os.path.join(dest_folder, file))
                    moved = True
                    print(f"File '{file}' moved to '{folder}' folder.")
                    break
            if not moved:
                print(f"File '{file}' does not match any rule, leaving in root.")





