import asyncio
import time
import google.generativeai as genai
import sys
from google.api_core.exceptions import ResourceExhausted
from config import API_KEY, LOAD_API_KEYS, GEMINI_MODEL
from .DataManager import DataManager


class AIManager:
    """AI 호출을 관리하는 클래스 - 비동기 처리 및 성능 모니터링 지원"""
    
    def __init__(self, debug=False, short_debug=False):
        self.debug = debug
        self.short_debug = short_debug
        self.call_stats = {
            'total_calls': 0,
            'total_time': 0,
            'parallel_calls': 0,
            'error_count': 0
        }
    
    @staticmethod
    def call_ai(prompt='테스트', system='지침', history=None, fine=None, api_key=None, retries=3, debug=False, call_info=None, suppress_individual_debug=False):
        if api_key is None:
            api_key = API_KEY['API_1']

        call_start = time.time()
        
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
                
                call_end = time.time()
                
                # 호출 정보 저장 (병렬 처리용)
                if call_info is not None:
                    call_info.update({
                        'api_key_type': 'LOAD' if api_key in LOAD_API_KEYS else 'MAIN',
                        'start_time': call_start,
                        'end_time': call_end,
                        'duration': call_end - call_start,
                        'result_length': len(result),
                        'success': True
                    })
                
                # call_info 업데이트 (병렬 호출용)
                if call_info is not None:
                    call_info.update({
                        'api_key_type': 'LOAD' if api_key in LOAD_API_KEYS else 'MAIN',
                        'start_time': call_start,
                        'end_time': call_end,
                        'duration': call_end - call_start,
                        'result_length': len(result),
                        'success': True
                    })
                
                # 단일 호출 시에만 간단한 디버그 출력 (병렬 호출에서는 억제)
                if debug and call_info is None and not suppress_individual_debug:
                    print(f"AI 호출 완료 ({call_end - call_start:.2f}초)")
                
                return result
            except ResourceExhausted as e:
                err_msg = f"[ERROR] AI API 호출이 너무 많아 오류가 발생했습니다: 429 = RPM초과 : {e}"
                print(err_msg)
                return err_msg
            except Exception as e:
                err_msg = f"[ERROR] AI API 호출 중 예외 발생: {e}"
                print(err_msg)
                return err_msg
    
    async def call_ai_async_single(self, prompt, system, history=None, fine=None, api_key=None, retries=3, suppress_individual_debug=False):
        """단일 AI 비동기 호출"""
        self.call_stats['total_calls'] += 1
        start_time = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self.call_ai, 
                prompt, system, history, fine, api_key, retries, self.debug, None, suppress_individual_debug
            )
            
            end_time = time.time()
            self.call_stats['total_time'] += (end_time - start_time)
            
            return result
        except Exception as e:
            self.call_stats['error_count'] += 1
            err_msg = f"[ERROR] 비동기 AI 호출 중 예외 발생: {e}"
            print(err_msg)
            return err_msg
    
    async def call_ai_async_multiple(self, queries, system_prompt, history=None, fine=None, label=None):
        """여러 LOAD API 키를 사용한 병렬 비동기 호출 (실시간 디버그 출력 지원)"""
        if not LOAD_API_KEYS or len(queries) <= 1:
            tasks = [self.call_ai_async_single(q, system_prompt, history, fine, API_KEY['API_1'], suppress_individual_debug=True) for q in queries]
            return await asyncio.gather(*tasks)

        self.call_stats['parallel_calls'] += 1
        start_time = time.time()

        call_infos = [{'query_index': i, 'query_preview': query[:50] + '...' if len(query) > 50 else query} 
                      for i, query in enumerate(queries)]
        
        if self.debug:
            label_str = f" ({label})" if label else ""
            print(f"병렬 AI 호출 시작 ({len(queries)}개){label_str}")

        async def run_and_debug(i, query):
            api_key = LOAD_API_KEYS[i % len(LOAD_API_KEYS)]
            call_info = call_infos[i]
            try:
                # 완전 비동기 방식으로 호출 (개별 디버그 메시지 억제)
                result = await self.call_ai_async_single(query, system_prompt, history, fine, api_key, suppress_individual_debug=True)
                return result
            except Exception as e:
                err_msg = f"[ERROR] 병렬 AI 호출 중 예외 발생 (TASK-{i+1:02d}): {e}"
                print(err_msg)
                return err_msg

        # 각 쿼리에 대해 run_and_debug 코루틴 생성
        tasks = [run_and_debug(i, q) for i, q in enumerate(queries)]
        
        # 모든 작업을 동시에 실행하고 결과 기다리기
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r is not None and r != "")

        if self.debug:
            end_time = time.time()
            total_duration = end_time - start_time
            success_count = sum(1 for r in results if r is not None and r != "")
            label_str = f" ({label})" if label else ""
            print(f"병렬 AI 호출 완료 ({total_duration:.2f}초)(성공 {success_count}/{len(queries)}){label_str}")

        return results
        """AI 호출 통계를 반환합니다."""
        avg_time = self.call_stats['total_time'] / max(self.call_stats['total_calls'], 1)
        return {
            'total_calls': self.call_stats['total_calls'],
            'total_time': self.call_stats['total_time'],
            'avg_time': avg_time,
            'parallel_calls': self.call_stats['parallel_calls'],
            'error_count': self.call_stats['error_count']
        }
