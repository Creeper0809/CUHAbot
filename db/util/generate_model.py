import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "../models")
INIT_FILE = os.path.join(MODELS_DIR, "__init__.py")

def generate_init():
    model_files = [
        f[:-3] for f in os.listdir(MODELS_DIR)
        if f.endswith(".py") and f != "__init__.py"
    ]

    with open(INIT_FILE, "w", encoding="utf-8") as f:
        f.write("# 자동 생성된 모델 import\n")
        for name in model_files:
            f.write(f"from .{name} import *\n")

    print(f"{INIT_FILE} 업데이트 ({len(model_files)}개 모델)")

if __name__ == "__main__":
    generate_init()
