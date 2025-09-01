"""
HSMS (Hierarchical Semantic Memory System) Package

계층적 의미 기억 시스템의 모든 클래스들을 포함하는 패키지입니다.

Classes:
    - DataManager: 데이터 관리 및 파일 입출력
    - MemoryNode: 개별 기억 노드
    - MemoryManager: 계층적 기억 트리 관리
    - AIManager: AI 호출 및 비동기 처리 관리
    - AuxiliaryAI: 보조 AI (핵심 분류 및 기억 처리)
    - MainAI: 메인 AI (사용자 대화 처리)
    - TreeCleanupEngine: 트리 정리 및 최적화 엔진
"""

from .DataManager import DataManager
from .MemoryNode import MemoryNode
from .MemoryManager import MemoryManager
from .AIManager import AIManager
from .AuxiliaryAI import AuxiliaryAI
from .MainAI import MainAI
from .TreeCleanupEngine import TreeCleanupEngine
from .SmartTopicUpdater import SmartTopicUpdater

__all__ = [
    'DataManager',
    'MemoryNode', 
    'MemoryManager',
    'AIManager',
    'AuxiliaryAI',
    'MainAI',
    'TreeCleanupEngine',
    'SmartTopicUpdater'
]

# 패키지 정보
__version__ = "1.0.0"
__author__ = "HSMS Development Team"
__description__ = "Hierarchical Semantic Memory System - AI 기반 계층적 기억 관리 시스템"
