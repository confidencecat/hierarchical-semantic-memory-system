import re
from .ConfigManager import ConfigManager


class CommandProcessor:
    """명령어 파싱 및 실행을 담당하는 클래스"""
    
    def __init__(self, config_manager, debug=False):
        self.config_manager = config_manager
        self.debug = debug
        self.commands = {
            'fanout': self._handle_fanout,
            'maxdepth': self._handle_max_depth,
            'model': self._handle_model,
            'k': self._handle_k_distance,
            'status': self._handle_status,
            'help': self._handle_help
        }
    
    async def process_command(self, command_text, user_permissions=None):
        """명령어를 파싱하고 실행합니다."""
        if not command_text.startswith('!'):
            return None
        
        # 명령어 파싱
        parts = command_text[1:].split()  # '!' 제거 후 분리
        if not parts:
            return "명령어를 입력해주세요. 도움말: !help"
        
        command = parts[0].lower()
        args = parts[1:]
        
        if command not in self.commands:
            return f"알 수 없는 명령어입니다: {command}. 도움말: !help"
        
        # 권한 검증 (관리자 명령어)
        admin_commands = {'fanout', 'maxdepth', 'model', 'k'}
        if command in admin_commands:
            if not user_permissions or not user_permissions.get('administrator', False):
                return "이 명령어는 관리자만 사용할 수 있습니다."
        
        try:
            return await self.commands[command](args)
        except Exception as e:
            if self.debug:
                print(f"Command processing error: {e}")
            return f"명령어 처리 중 오류가 발생했습니다: {e}"
    
    async def _handle_fanout(self, args):
        """팬아웃 제한 설정 변경"""
        if not args:
            current = self.config_manager.get('fanout_limit')
            return f"현재 팬아웃 제한: {current}"
        
        try:
            value = int(args[0])
            if value < 1 or value > 20:
                return "팬아웃 값은 1-20 사이여야 합니다."
            
            self.config_manager.set('fanout_limit', value)
            return f"팬아웃 제한을 {value}로 변경했습니다."
        except ValueError:
            return "올바른 숫자를 입력해주세요."
    
    async def _handle_max_depth(self, args):
        """최대 트리 깊이 설정 변경"""
        if not args:
            current = self.config_manager.get('max_depth')
            return f"현재 최대 트리 깊이: {current}"
        
        try:
            value = int(args[0])
            if value < 3 or value > 10:
                return "최대 깊이 값은 3-10 사이여야 합니다."
            
            self.config_manager.set('max_depth', value)
            return f"최대 트리 깊이를 {value}로 변경했습니다."
        except ValueError:
            return "올바른 숫자를 입력해주세요."
    
    async def _handle_model(self, args):
        """AI 모델 설정 변경"""
        valid_models = ['gemini-1.5-flash', 'gemini-2.5-flash', 'gemini-pro']
        
        if not args:
            current = self.config_manager.get('api_model')
            return f"현재 AI 모델: {current}"
        
        model_name = args[0]
        if model_name not in valid_models:
            return f"지원되는 모델: {', '.join(valid_models)}"
        
        self.config_manager.set('api_model', model_name)
        return f"AI 모델을 {model_name}으로 변경했습니다."
    
    async def _handle_k_distance(self, args):
        """K-거리 검색 설정 변경"""
        if not args:
            current = self.config_manager.get('k_distance')
            return f"현재 K-거리 검색 값: {current}"
        
        try:
            value = int(args[0])
            if value < 1 or value > 10:
                return "K 값은 1-10 사이여야 합니다."
            
            self.config_manager.set('k_distance', value)
            return f"K-거리 검색 값을 {value}로 변경했습니다."
        except ValueError:
            return "올바른 숫자를 입력해주세요."
    
    async def _handle_status(self, args):
        """현재 설정 상태 표시"""
        config = self.config_manager.get_all_config()
        status_lines = [
            "--- 현재 설정 상태 ---",
            f"팬아웃 제한: {config.get('fanout_limit', 'N/A')}",
            f"최대 트리 깊이: {config.get('max_depth', 'N/A')}",
            f"K-거리 검색: {config.get('k_distance', 'N/A')}",
            f"AI 모델: {config.get('api_model', 'N/A')}",
            f"최대 요약 길이: {config.get('max_summary_length', 'N/A')}",
            "--------------------"
        ]
        return "\n".join(status_lines)
    
    async def _handle_help(self, args):
        """도움말 표시"""
        help_lines = [
            "--- 명령어 도움말 ---",
            "!fanout [숫자] - 팬아웃 제한 설정 (관리자)",
            "!maxdepth [숫자] - 최대 트리 깊이 설정 (관리자)",
            "!model [모델명] - AI 모델 설정 (관리자)",
            "!k [숫자] - K-거리 검색 설정 (관리자)",
            "!status - 현재 설정 상태 표시",
            "!help - 이 도움말 표시",
            "--------------------"
        ]
        return "\n".join(help_lines)
