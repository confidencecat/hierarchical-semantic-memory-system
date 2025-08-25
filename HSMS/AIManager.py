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
    def call_ai(prompt='테스트', system='지침', history=None, fine=None, api_key=None, retries=3, debug=False, call_info=None):
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
                
                # 단일 호출 시에만 즉시 디버그 출력
                if debug and call_info is None:
                    print(f"      ┌─ [AI-CALL] 호출 시작")
                    print(f"      │  API키: {'LOAD' if api_key in LOAD_API_KEYS else 'MAIN'}")
                    print(f"      └─ 처리 중...")
                    
                    print(f"\n===========> AI 호출 상세 정보 ===========>")
                    print(f"시스템 프롬프트:")
                    print(f"{system}")
                    print(f"\n사용자 프롬프트:")
                    print(f"{prompt}")
                    if fine:
                        print(f"\nFine-tuning 데이터: {len(fine)}개 예시")
                    print(f"==========================================>")
                    
                    print(f"\n===========> AI 응답 결과 ===========>")
                    print(f"소요시간: {call_end - call_start:.2f}초")
                    print(f"응답:")
                    print(f"{result}")
                    print(f"====================================>")
                    
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
                    if call_info is not None:
                        call_info.update({
                            'success': False,
                            'error': f'재시도 한계 도달: {retries}번'
                        })
                    return ''
                wait = 2 ** attempt
                time.sleep(wait)
            except Exception as e:
                if call_info is not None:
                    call_info.update({
                        'success': False,
                        'error': str(e)
                    })
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
                prompt, system, history, fine, api_key, retries, self.debug, None
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
        """여러 LOAD API 키를 사용한 병렬 비동기 호출 (실시간 디버그 출력 지원)"""
        if not LOAD_API_KEYS or len(queries) <= 1:
            tasks = [self.call_ai_async_single(q, system_prompt, history, fine, API_KEY['API_1']) for q in queries]
            return await asyncio.gather(*tasks)

        self.call_stats['parallel_calls'] += 1
        start_time = time.time()

        call_infos = [{'query_index': i, 'query_preview': query[:50] + '...' if len(query) > 50 else query} 
                      for i, query in enumerate(queries)]
        
        if self.debug:
            print(f"===========> AI 병렬 호출 시작 ({len(queries)}개) ===========>")
            for i, call_info in enumerate(call_infos):
                api_key_type = 'LOAD' if LOAD_API_KEYS[i % len(LOAD_API_KEYS)] in LOAD_API_KEYS else 'MAIN'
                print(f"  [TASK-{i+1:02d}] API: {api_key_type}, QUERY: \"{call_info['query_preview']}\"")
            print(f"======================================================>")

        async def run_and_debug(i, query):
            api_key = LOAD_API_KEYS[i % len(LOAD_API_KEYS)]
            call_info = call_infos[i]
            
            try:
                # asyncio.to_thread를 사용하여 블로킹 함수를 비동기적으로 실행
                result = await asyncio.to_thread(
                    self.call_ai, query, system_prompt, history, fine, api_key, 3, False, call_info
                )
                
                if self.debug:
                    duration = call_info.get('duration', 0)
                    response_type = "True" if result.lower() == 'true' else ("False" if result.lower() == 'false' else f"{len(result)}자")
                    print(f"  [DONE] [TASK-{i+1:02d}] 완료 ({duration:.2f}초) - 결과: {response_type}")
                
                return result
            except Exception as e:
                if self.debug:
                    print(f"  [FAIL] [TASK-{i+1:02d}] 실패 - 오류: {e}")
                return "" # 실패 시 빈 문자열 반환

        # 각 쿼리에 대해 run_and_debug 코루틴 생성
        tasks = [run_and_debug(i, q) for i, q in enumerate(queries)]
        
        # 모든 작업을 동시에 실행하고 결과 기다리기
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r is not None and r != "")

        if self.debug:
            end_time = time.time()
            total_duration = end_time - start_time
            print(f"===========> AI 병렬 호출 완료 ({total_duration:.2f}초) ===========>")
            print(f"  - 성공률: {success_count}/{len(queries)} ({success_count/len(queries)*100:.1f}%)")
            if len(queries) > 0:
                print(f"  - 평균 처리 시간 (개별): {total_duration/len(queries):.2f}초/쿼리")
            print(f"======================================================>")

        return results
    
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
