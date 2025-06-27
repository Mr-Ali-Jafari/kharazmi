from pathlib import Path

def convert_imports_to_relative(project_path):
    """
    تبدیل ایمپورت‌های مطلق به ایمپورت نسبی در فایل‌های پایتون پروژه
    """
    for file in Path(project_path).rglob('*.py'):
        with open(file, 'r') as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            # اگر خط با from شروع شود و شامل 'project.' باشد، تبدیل به ایمپورت نسبی شود
            if line.startswith('from') and 'project.' in line:
                new_line = line.replace('from project.', 'from .')
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        with open(file, 'w') as f:
            f.writelines(new_lines)

