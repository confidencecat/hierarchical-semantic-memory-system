import asyncio
import time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from config import API_KEY, LOAD_API_KEYS, GEMINI_MODEL
from .DataManager import DataManager


class AIManager:
    """AI 호출을 관리하는 클래스 - 비동기 처리 지원"""
    
    @staticmethod
    def call_ai(prompt='테스트', system='지침', history=None, fine=None, api_key=None, retries=3):
        if api_key is None:
            api_key = API_KEY['API_1']

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
                return result
            except ResourceExhausted:
                attempt += 1
                if attempt > retries:
                    return ''
                wait = 2 ** attempt
                time.sleep(wait)
            except Exception as e:
                print(f"AI 호출 중 오류 발생: {e}")
                return ''
    
    @staticmethod
    async def call_ai_async_single(prompt, system, history=None, fine=None, api_key=None, retries=3):
        """단일 AI 비동기 호출"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            AIManager.call_ai, 
            prompt, system, history, fine, api_key, retries
        )
    
    @staticmethod
    async def call_ai_async_multiple(queries, system_prompt, history=None, fine=None):
        """여러 LOAD API 키를 사용한 병렬 비동기 호출"""
        if not LOAD_API_KEYS:
            # LOAD API 키가 없으면 기본 API 사용
            tasks = []
            for query in queries:
                task = AIManager.call_ai_async_single(
                    query, system_prompt, history, fine, API_KEY['API_1']
                )
                tasks.append(task)
            return await asyncio.gather(*tasks)
        
        # LOAD API 키들을 사용한 병렬 처리
        tasks = []
        for i, query in enumerate(queries):
            api_key = LOAD_API_KEYS[i % len(LOAD_API_KEYS)]  # 라운드 로빈 방식
            task = AIManager.call_ai_async_single(
                query, system_prompt, history, fine, api_key
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
