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
        
        # 각 호출의 정보를 저장할 딕셔너리들
        call_infos = [{'query_index': i, 'query_preview': query[:50] + '...' if len(query) > 50 else query} 
                     for i, query in enumerate(queries)]
        
        tasks = []
        for i, query in enumerate(queries):
            api_key = LOAD_API_KEYS[i % len(LOAD_API_KEYS)]  # 라운드 로빈 방식
            call_info = call_infos[i]  # 각 호출의 정보를 전달
            
            loop = asyncio.get_event_loop()
            task = loop.run_in_executor(
                None, 
                self.call_ai, 
                query, system_prompt, history, fine, api_key, 3, False, call_info
            )
            tasks.append(task)
        
        # 병렬 시작 메시지 (디버그 모드일 때만)
        if self.debug:
            print(f"===========> AI 병렬 호출 시작 ===========>")
            print(f"호출 수량: {len(queries)}개")
            print(f"사용 API 키: {len(LOAD_API_KEYS)}개")
            for i, call_info in enumerate(call_infos):
                api_key_type = 'LOAD' if LOAD_API_KEYS[i % len(LOAD_API_KEYS)] in LOAD_API_KEYS else 'MAIN'
                print(f"  {i+1}. API키: {api_key_type}, 쿼리: {call_info['query_preview']}")
            print(f"=========================================>")
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 처리 및 통계
        successful_results = []
        success_count = 0
        error_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                call_infos[i]['success'] = False
                call_infos[i]['error'] = str(result)
                successful_results.append('')  # Empty result for failed queries
                error_count += 1
            else:
                successful_results.append(result)
                success_count += 1
        
        # 병렬 완료 메시지 (디버그 모드일 때만)
        if self.debug:
            end_time = time.time()
            print(f"===========> AI 병렬 호출 완료 ===========>")
            print(f"총 소요시간: {end_time - start_time:.2f}초")
            print(f"성공률: {success_count}/{len(queries)}개")
            print(f"평균 소요시간: {(end_time - start_time)/len(queries):.2f}초")
            
            # 각 호출의 상세 정보 출력
            for i, call_info in enumerate(call_infos):
                if 'duration' in call_info:
                    response_type = ""
                    if successful_results[i].lower() == 'true':
                        response_type = "True"
                    elif successful_results[i].lower() == 'false':
                        response_type = "False"
                    else:
                        response_type = f"{len(successful_results[i])}자"
                    
                    print(f"  {i+1}. API키: {call_info.get('api_key_type', 'UNKNOWN')}, "
                          f"시간: {call_info['duration']:.2f}초, "
                          f"결과: {response_type}")
                else:
                    print(f"  {i+1}. 실패: {call_info.get('error', '알 수 없는 오류')}")
            print(f"=========================================>")
        
        return successful_results
        
        # Filter out exceptions and log them
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                successful_results.append('')  # Empty result for failed queries
            else:
                successful_results.append(result)
        
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
