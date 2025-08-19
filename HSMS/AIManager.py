import asyncio
import time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from config import API_KEY, LOAD_API_KEYS, GEMINI_MODEL
from .DataManager import DataManager


class AIManager:
    """AI 호출을 관리하는 클래스 - 비동기 처리 및 성능 모니터링 지원"""
    
    def __init__(self, debug=False):
        self.debug = debug
        self.call_stats = {
            'total_calls': 0,
            'total_time': 0,
            'parallel_calls': 0,
            'error_count': 0
        }
    
    @staticmethod
    def call_ai(prompt='테스트', system='지침', history=None, fine=None, api_key=None, retries=3, debug=False):
        if api_key is None:
            api_key = API_KEY['API_1']

        if debug:
            call_start = time.time()
            print(f"      ┌─ [AI-CALL] 호출 시작")
            print(f"      │  프롬프트: '{prompt[:50]}{'...' if len(prompt) > 50 else ''}'")
            print(f"      │  API키: {'LOAD' if api_key in LOAD_API_KEYS else 'MAIN'}")
            print(f"      └─ 처리 중...")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=system)

        if fine:
            ex = ''.join([f"user: {q}\nassistant: {a}\n" for q, a in fine])
            combined = f"{ex}user: {prompt}"
        else:
            his = DataManager.history_str(history if history is not None else [])
            combined = f"{his}user: {prompt}"

        attempt = 0
        while True:
            try:
                resp = model.start_chat(history=[]).send_message(combined)
                txt = resp._result.candidates[0].content.parts[0].text.strip()
                result = txt[9:].strip() if txt.lower().startswith('assistant:') else txt
                
                if debug:
                    call_end = time.time()
                    response_info = ""
                    if result.lower() == 'true':
                        response_info = "True"
                    elif result.lower() == 'false':
                        response_info = "False"
                    else:
                        response_info = f"{len(result)}자"
                    print(f"      ┌─ [AI-CALL] 호출 완료")
                    print(f"      │  소요시간: {call_end - call_start:.2f}초")
                    print(f"      │  응답타입: {response_info}")
                    print(f"      └─ 완료")
                
                return result
            except ResourceExhausted:
                attempt += 1
                if attempt > retries:
                    if debug:
                        print(f"      └─ [AI-ERROR] 재시도 한계 도달: {retries}번")
                    return ''
                wait = 2 ** attempt
                if debug:
                    print(f"      │  [AI-RETRY] 할당량 초과, {wait}초 대기 (시도 {attempt}/{retries})")
                time.sleep(wait)
            except Exception as e:
                if debug:
                    print(f"      └─ [AI-ERROR] 오류 발생: {e}")
                print(f"AI 호출 중 오류 발생: {e}")
                return ''
    
    async def call_ai_async_single(self, prompt, system, history=None, fine=None, api_key=None, retries=3):
        """단일 AI 비동기 호출"""
        self.call_stats['total_calls'] += 1
        start_time = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self.call_ai, 
                prompt, system, history, fine, api_key, retries, self.debug
            )
            
            end_time = time.time()
            self.call_stats['total_time'] += (end_time - start_time)
            
            return result
        except Exception as e:
            self.call_stats['error_count'] += 1
            if self.debug:
                print(f"      └─ [ASYNC-ERROR] 비동기 호출 오류: {e}")
            return ''
    
    async def call_ai_async_multiple(self, queries, system_prompt, history=None, fine=None):
        """여러 LOAD API 키를 사용한 병렬 비동기 호출"""
        if not LOAD_API_KEYS:
            # LOAD API 키가 없으면 기본 API 사용
            tasks = []
            for query in queries:
                task = self.call_ai_async_single(
                    query, system_prompt, history, fine, API_KEY['API_1']
                )
                tasks.append(task)
            return await asyncio.gather(*tasks)
        
        # LOAD API 키들을 사용한 병렬 처리
        self.call_stats['parallel_calls'] += 1
        start_time = time.time()
        
        if self.debug:
            print(f"    ┌─ [PARALLEL] 병렬 호출 시작")
            print(f"    │  쿼리 수: {len(queries)}개")
            print(f"    │  API 키: {len(LOAD_API_KEYS)}개")
            print(f"    └─ 처리 중...")
        
        tasks = []
        for i, query in enumerate(queries):
            api_key = LOAD_API_KEYS[i % len(LOAD_API_KEYS)]  # 라운드 로빈 방식
            task = self.call_ai_async_single(
                query, system_prompt, history, fine, api_key
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log them
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                if self.debug:
                    print(f"    │  [PARALLEL-ERROR] 쿼리 {i} 실패: {result}")
                successful_results.append('')  # Empty result for failed queries
            else:
                successful_results.append(result)
        
        if self.debug:
            end_time = time.time()
            success_count = len([r for r in successful_results if r])
            print(f"    ┌─ [PARALLEL] 병렬 호출 완료")
            print(f"    │  소요시간: {end_time - start_time:.2f}초")
            print(f"    │  성공률: {success_count}/{len(queries)}개")
            print(f"    └─ 완료")
        
        return successful_results
    
    def get_stats(self):
        """AI 호출 통계를 반환합니다."""
        avg_time = self.call_stats['total_time'] / max(self.call_stats['total_calls'], 1)
        return {
            'total_calls': self.call_stats['total_calls'],
            'total_time': self.call_stats['total_time'],
            'avg_time': avg_time,
            'parallel_calls': self.call_stats['parallel_calls'],
            'error_count': self.call_stats['error_count']
        }
