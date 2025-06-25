import os

def detect_framework(project_path):
    if any(file.endswith('.kv') for file in os.listdir(project_path)):
        return "Kivy"
    elif 'app.py' in os.listdir(project_path):
        return "Flask"
    elif any(file.endswith('.ui') for file in os.listdir(project_path)):
        return "PyQt5"
    elif any(file.endswith('.py') and 'pygame' in open(os.path.join(project_path, file)).read() 
             for file in os.listdir(project_path)):
        return "Pygame"
    return "Unknown"

