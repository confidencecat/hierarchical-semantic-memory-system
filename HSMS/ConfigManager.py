import json
import os
from config import CONFIG_JSON_PATH, DEFAULT_CONFIG


class ConfigManager:
    """설정 변경 추적 및 자동 저장을 담당하는 클래스"""
    
    def __init__(self, debug=False):
        self.debug = debug
        self.config_data = self._load_config()
        self.change_listeners = []  # 설정 변경 이벤트 리스너
    
    def _load_config(self):
        """config.json 파일을 로드합니다."""
        try:
            with open(CONFIG_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 누락된 값은 기본값으로 채움
            for key, value in DEFAULT_CONFIG.items():
                if key not in data:
                    data[key] = value
            return data
        except (FileNotFoundError, json.JSONDecodeError):
            return DEFAULT_CONFIG.copy()
    
    def _save_config(self):
        """설정 데이터를 config.json 파일에 저장합니다."""
        with open(CONFIG_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.config_data, f, ensure_ascii=False, indent=2)
    
    def get(self, key):
        """설정 값을 가져옵니다."""
        return self.config_data.get(key, DEFAULT_CONFIG.get(key))
    
    def set(self, key, value):
        """설정 값을 변경하고 파일에 저장합니다."""
        old_value = self.get(key)
        if old_value != value:
            self.config_data[key] = value
            self._save_config()
            
            if self.debug:
                print(f"Config updated: {key} = {value}")
            
            # 변경 이벤트 발생
            self._notify_change(key, old_value, value)
    
    def update_from_args(self, args):
        """argparse로 받은 인자를 설정에 반영하고 저장합니다."""
        changed = False
        args_dict = vars(args)
        
        # 특별 매핑: k -> k_distance
        if hasattr(args, 'k') and args.k is not None:
            args_dict['k_distance'] = args.k
        
        for key in DEFAULT_CONFIG:
            if key in args_dict and args_dict[key] is not None:
                if self.get(key) != args_dict[key]:
                    self.set(key, args_dict[key])
                    changed = True
        
        if changed and self.debug:
            print("Configuration saved from args.")
    
    def add_change_listener(self, listener):
        """설정 변경 이벤트 리스너를 추가합니다."""
        self.change_listeners.append(listener)
    
    def remove_change_listener(self, listener):
        """설정 변경 이벤트 리스너를 제거합니다."""
        if listener in self.change_listeners:
            self.change_listeners.remove(listener)
    
    def _notify_change(self, key, old_value, new_value):
        """설정 변경을 모든 리스너에게 알립니다."""
        for listener in self.change_listeners:
            try:
                listener(key, old_value, new_value)
            except Exception as e:
                if self.debug:
                    print(f"Error notifying change listener: {e}")
    
    def validate_config(self):
        """설정 값들의 유효성을 검증합니다."""
        errors = []
        
        # k_distance 검증
        k_distance = self.get('k_distance')
        if not isinstance(k_distance, int) or k_distance < 1 or k_distance > 50:
            errors.append(f"k_distance must be integer between 1 and 50, got {k_distance}")
        
        # fanout_limit 검증
        fanout_limit = self.get('fanout_limit')
        if not isinstance(fanout_limit, int) or fanout_limit < 1 or fanout_limit > 20:
            errors.append(f"fanout_limit must be integer between 1 and 20, got {fanout_limit}")
        
        # max_depth 검증
        max_depth = self.get('max_depth')
        if not isinstance(max_depth, int) or max_depth < 3 or max_depth > 10:
            errors.append(f"max_depth must be integer between 3 and 10, got {max_depth}")
        
        # max_summary_length 검증
        max_summary_length = self.get('max_summary_length')
        if not isinstance(max_summary_length, int) or max_summary_length < 100 or max_summary_length > 2000:
            errors.append(f"max_summary_length must be integer between 100 and 2000, got {max_summary_length}")
        
        return errors
    
    def reset_to_defaults(self):
        """설정을 기본값으로 리셋합니다."""
        old_config = self.config_data.copy()
        self.config_data = DEFAULT_CONFIG.copy()
        self._save_config()
        
        if self.debug:
            print("Configuration reset to defaults")
        
        # 모든 변경사항에 대해 이벤트 발생
        for key, new_value in DEFAULT_CONFIG.items():
            old_value = old_config.get(key)
            if old_value != new_value:
                self._notify_change(key, old_value, new_value)
    
    def get_all_config(self):
        """모든 설정 값을 반환합니다."""
        return self.config_data.copy()
