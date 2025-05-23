import os

def main():

    script_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.normpath(os.path.join(script_dir, os.pardir))
    init_path = os.path.join(models_dir, "__init__.py")

    module_files = [
        f for f in os.listdir(models_dir)
        if f.endswith(".py") and f != "__init__.py"
    ]
    module_names = sorted(name[:-3] for name in module_files)

    with open(init_path, "w", encoding="utf-8") as fw:
        fw.write("# Auto-generated by generate_init.py\n\n")
        for mod in module_names:
            fw.write(f"from .{mod} import *\n")

    print(f"[OK] {init_path} updated ({len(module_names)} modules).")

if __name__ == "__main__":
    main()
