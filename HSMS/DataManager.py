import json
import os


class DataManager:
    """데이터 관리를 담당하는 클래스 - 파일 입출력 및 메모리 관리"""
    
    @staticmethod
    def load_json(file):
        if os.path.exists(file):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        return []
                    return json.loads(content)
            except json.JSONDecodeError as e:
                print(f"JSON 파일 파싱 오류 ({file}): {e}")
                print("손상된 JSON 파일을 백업하고 새로 시작합니다.")
                
                # 백업 파일 생성
                backup_file = f"{file}.backup"
                if os.path.exists(file):
                    with open(file, 'r', encoding='utf-8') as f:
                        backup_content = f.read()
                    with open(backup_file, 'w', encoding='utf-8') as f:
                        f.write(backup_content)
                    print(f"백업 파일 생성: {backup_file}")
                
                return []
            except Exception as e:
                print(f"파일 읽기 오류 ({file}): {e}")
                return []
        return []

    @staticmethod
    def save_json(file, data):
        folder = os.path.dirname(file)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def history_str(buf):
        s = ''
        for it in buf:
            if isinstance(it, list):
                for sub in it:
                    s += f"{sub['role']}: {sub['content']}\n"
            elif isinstance(it, dict):
                s += f"{it['role']}: {it['content']}\n"
        return s
