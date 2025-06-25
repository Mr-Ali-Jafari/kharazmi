import argparse
from core.framework_detector import detect_framework
from core.import_manager import convert_imports_to_relative
from core.project_organizer import create_structure,categorize_files


def main():
    parser = argparse.ArgumentParser(description="ابزار مدیریت پروژه پایتون")
    parser.add_argument("--project", required=True, help="مسیر پروژه")
    parser.add_argument("--fix-imports", action="store_true", help="تبدیل ایمپورت‌ها به نسبی")
    parser.add_argument("--suggest-structure", action="store_true", help="پیشنهاد یا ایجاد ساختار پروژه")
    
    args = parser.parse_args()
    
    framework = detect_framework(args.project)
    print(f"فریم‌ورک تشخیص داده شده: {framework}")
    
    if args.fix_imports:
        print("تبدیل ایمپورت‌ها به نسبی...")
        convert_imports_to_relative(args.project)
        print("ایمپورت‌ها با موفقیت تبدیل شدند!")
    
    if args.suggest_structure:
        print("ایجاد ساختار پیشنهادی...")
        create_structure(args.project, framework)
        categorize_files(args.project)

        print("ساختار پروژه ایجاد شد!")

if __name__ == "__main__":
    main()

