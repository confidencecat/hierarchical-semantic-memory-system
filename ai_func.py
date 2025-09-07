import asyncio
import time
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from config import AI_API, LOAD_API, AI_API_N, LOAD_API_N, CALL_STATS, debug_print, GEMINI_MODEL
from memory import load_json

# 기본 동기 AI 호출 함수
def AI(prompt: str = '테스트', system: str = '지침', history: list = None, fine: list = None, 
       api_key: str = None, retries: int = 3, debug: bool = False) -> str:
    """
    기본적인 gemini API 단일(동기적) 호출 함수
    """
    if api_key is None:
        if AI_API_N > 0:
            api_key = AI_API[0]
        else:
            return "[ERROR] No AI API key available"
    
    call_start = time.time()
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            GEMINI_MODEL, 
            system_instruction=system,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        # 히스토리 처리
        if fine:
            ex = ''.join([f"user: {q}\nassistant: {a}\n" for q, a in fine])
            combined = f"{ex}user: {prompt}"
        else:
            his = ""
            if history:
                for msg in history:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    his += f"{role}: {content}\n"
            combined = f"{his}user: {prompt}"
        
        resp = model.start_chat(history=[]).send_message(combined)
        txt = resp._result.candidates[0].content.parts[0].text.strip()
        result = txt[10:].strip() if txt.lower().startswith('assistant:') else txt
        
        call_end = time.time()
        
        if debug:
            debug_print(f"AI 호출 완료 (응답 길이: {len(result)}자, 소요시간: {call_end - call_start:.2f}초)")
        
        return result
        
    except Exception as e:
        if "429" in str(e) or "ResourceExhausted" in str(e):
            err_msg = f"[ERROR] AI API 호출이 너무 많아 오류가 발생했습니다: 429 = RPM초과 : {e}"
        else:
            err_msg = f"[ERROR] AI API 호출 중 예외 발생: {e}"
        
        if debug:
            debug_print(err_msg)
        return err_msg

# 비동기 AI 호출 함수
async def ASYNC_AI(prompt: str, system: str, history: list = None, fine: list = None, 
                   api_key: str = None, retries: int = 3, debug: bool = False) -> str:
    """
    기본적인 gemini 단일(비동기적) 호출 함수
    """
    global CALL_STATS
    CALL_STATS['total_calls'] += 1
    start_time = time.time()
    
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            AI, 
            prompt, system, history, fine, api_key, retries, debug
        )
        
        end_time = time.time()
        CALL_STATS['total_time'] += (end_time - start_time)
        
        return result
    except Exception as e:
        CALL_STATS['error_count'] += 1
        err_msg = f"[ERROR] 비동기 AI 호출 중 예외 발생: {e}"
        if debug:
            debug_print(err_msg)
        return err_msg

# 병렬 AI 호출 함수
async def ASYNC_MULTI_AI(queries: list, system_prompt: str, history: list = None, fine: list = None, 
                         debug: bool = False, start_debug_message: str = "--start", 
                         end_debug_message: str = "--end") -> list:
    """
    여러 쿼리의 병렬(비동기적) 처리
    """
    global CALL_STATS
    
    if not queries:
        return []
    
    if not LOAD_API or len(queries) <= 1:
        tasks = [ASYNC_AI(q, system_prompt, history, fine, AI_API[0] if AI_API_N > 0 else None, debug=debug) for q in queries]
        return await asyncio.gather(*tasks)
    
    CALL_STATS['parallel_calls'] += 1
    start_time = time.time()
    
    if debug:
        debug_print(start_debug_message)
        debug_print(f"병렬 AI 호출 시작 ({len(queries)}개)")
    
    async def run_and_debug(i, query):
        api_key = LOAD_API[i % len(LOAD_API)]
        try:
            result = await ASYNC_AI(query, system_prompt, history, fine, api_key, debug=debug)
            return result
        except Exception as e:
            err_msg = f"[ERROR] 병렬 AI 호출 중 예외 발생 (TASK-{i+1:02d}): {e}"
            if debug:
                debug_print(err_msg)
            return err_msg
    
    tasks = [run_and_debug(i, q) for i, q in enumerate(queries)]
    results = await asyncio.gather(*tasks)
    
    if debug:
        end_time = time.time()
        total_duration = end_time - start_time
        success_count = sum(1 for r in results if r and not r.startswith("[ERROR]"))
        debug_print(f"병렬 AI 호출 완료 ({total_duration:.2f}초)(성공 {success_count}/{len(queries)})")
        debug_print(end_debug_message)
    
    return results

# 기억 필요성 판단 AI
def need_memory_judgement_AI(user_input: str) -> bool:
    """
    사용자 질문에 대한 기억 검색 필요성 판단
    """
    system_prompt = """사용자의 발언에 응답하기 위해서 과거의 대화가 필요한지 판단해라.

다음 경우에는 반드시 "True"를 출력하라:
- 사용자가 "저번에", "이전에", "과거에", "전에" 등의 단어를 사용하여 과거 대화를 언급하는 경우
- 사용자가 "내가 이야기했던", "내가 말했던", "우리가 나눴던" 등의 표현으로 이전 대화를 참조하는 경우
- 사용자가 "정리해줘", "요약해줘", "다시 보여줘" 등의 표현으로 과거 정보를 요청하는 경우
- 사용자가 구체적인 과거 주제나 대화를 언급하는 경우

다음 경우에는 "False"를 출력하라:
- 일반적인 질문이나 정보 요청
- 현재 시점의 문제 해결
- 미래 계획이나 예측에 대한 질문

출력은 반드시 "True" 또는 "False"로만 하라."""
    
    prompt = f"사용자 발언:\n{user_input}"
    
    debug_print("기억 필요성 판단 중...")
    
    result = AI(prompt, system_prompt, debug=True)
    result = result.strip().lower()
    
    debug_print(f"기억 필요성 판단 결과: {result}")
    
    return result == 'true'

# 최종 응답 생성 AI
def respond_AI(user_input: str, memory: list = None) -> str:
    """
    사용자 질문에 대한 최종 응답 생성
    """
    system_prompt = """사용자의 발화에 응답해라. 과거 대화가 주어진다면 그 대화를 기반으로 응답해라. 간단하게 응답해라."""
    prompt = ""
    
    if memory:
        all_memory = load_json('memory/all_memory.json', [])
        for idx in memory:
            if 0 <= idx < len(all_memory):
                conversation = all_memory[idx]
                prompt += f"\n==================================[ {idx} 번 ]==================================\n"
                for msg in conversation:
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    if role == 'user':
                        prompt += f"user : {content}\n"
                    elif role == 'assistant':
                        prompt += f"AI   : {content}\n"
                prompt += "============================================================================\n"
    
    prompt += f"\n{user_input}"
    
    debug_print("최종 응답 생성 중...")
    
    result = AI(prompt, system_prompt, debug=True)
    
    debug_print(f"최종 응답 생성 완료 (응답 길이: {len(result)}자)")
    
    return result

# 단일 노드 유사도 판단 AI
def judgement_similar_AI(current_conversation: str, node_id: str) -> str:
    """
    단일 노드와 현재 대화의 유사도 판단
    """
    from memory import get_node_data
    
    system_prompt = """노드의 주제와 요약을 보고 사용자 질문과의 관련성을 0.0~1.0 사이의 점수로 평가해라.
- 0.9 이상: 매우 강한 관련성 (같은 구체적 주제)
- 0.7~0.8: 강한 관련성 (같은 카테고리의 세부 주제)
- 0.5~0.6: 보통 관련성 (같은 큰 분야이지만 다른 세부 주제)
- 0.3~0.4: 약한 관련성 (넓은 의미로만 관련)
- 0.2 이하: 관련성 없음

점수만 숫자로 출력하세요 (예: 0.85)"""
    
    node_data = get_node_data(node_id)
    if not node_data:
        return "0.0"
    
    topic = node_data.get('topic', '')
    summary = node_data.get('summary', '')
    node_summation = f"주제: {topic}\n요약: {summary}"
    
    prompt = f"노드 정보 : {node_summation}\n현재 대화 : {current_conversation}\n\n위 노드와 현재 대화의 유사도를 0.0~1.0 점수로 평가하세요."
    
    result = AI(prompt, system_prompt)
    return result.strip()

# 병렬 노드 유사도 판단 AI
async def judgement_similar_multi_AI(node_ids: list, current_conversation: str) -> list:
    """
    여러 노드와 현재 대화의 유사도를 병렬로 판단
    """
    from memory import get_node_data
    
    system_prompt = """노드의 주제와 요약을 보고 사용자 질문과의 관련성을 0.0~1.0 사이의 점수로 평가해라.
- 0.9 이상: 매우 강한 관련성 (같은 구체적 주제)
- 0.7~0.8: 강한 관련성 (같은 카테고리의 세부 주제)
- 0.5~0.6: 보통 관련성 (같은 큰 분야이지만 다른 세부 주제)
- 0.3~0.4: 약한 관련성 (넓은 의미로만 관련)
- 0.2 이하: 관련성 없음

점수만 숫자로 출력하세요 (예: 0.85)"""
    
    queries = []
    for node_id in node_ids:
        node_data = get_node_data(node_id)
        if node_data:
            topic = node_data.get('topic', '')
            summary = node_data.get('summary', '')
            node_summation = f"주제: {topic}\n요약: {summary}"
            prompt = f"노드 정보 : {node_summation}\n현재 대화 : {current_conversation}\n\n위 노드와 현재 대화의 유사도를 0.0~1.0 점수로 평가하세요."
            queries.append(prompt)
        else:
            queries.append("0.0")  # 노드가 없으면 0.0
    
    start_debug_message = "=============[ judgement_similar_AI ]============= [ START ]"
    end_debug_message = "=============[ judgement_similar_AI ]============= [  END  ]"
    
    results = await ASYNC_MULTI_AI(
        queries, system_prompt, debug=True, 
        start_debug_message=start_debug_message, 
        end_debug_message=end_debug_message
    )
    
    # 유사도 점수 통계 출력
    scores = []
    for result in results:
        try:
            score = float(result)
            scores.append(score)
        except:
            scores.append(0.0)
    
    if scores:
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        debug_print(f"유사도 비교 완료 - 평균: {avg_score:.2f}, 최고: {max_score:.2f} ({len(node_ids)}개 노드)")
    
    return results

# 클러스터링 AI
async def clustering_AI(candidate_node_ids: list, current_conversation: str, fanout_limit: int) -> tuple:
    """
    클러스터링 대상 노드 선택 및 새 부모 노드 주제 생성
    """
    from memory import get_node_data
    
    system_prompt = f"""다음 노드들 중에서 현재 대화와 가장 유사한 노드들을 최대 {fanout_limit-1}개 선택하고, 
선택된 노드들과 현재 대화를 포괄하는 새로운 주제명을 생성해라.

출력 형식:
선택된 노드 ID들: [id1, id2, ...]
새 주제명: 간결한 주제명"""
    
    prompt = f"현재 대화: {current_conversation}\n\n후보 노드들:\n"
    for node_id in candidate_node_ids:
        node_data = get_node_data(node_id)
        if node_data:
            topic = node_data.get('topic', '')
            summary = node_data.get('summary', '')
            prompt += f"노드 ID: {node_id}\n주제: {topic}\n요약: {summary}\n\n"
    
    result = AI(prompt, system_prompt)
    
    # 결과 파싱 (간단한 파싱, 실제로는 더 정교하게 해야 함)
    lines = result.split('\n')
    selected_ids = []
    new_topic = "새 주제"
    
    for line in lines:
        if "선택된 노드" in line or "ID" in line:
            # 간단한 ID 추출
            for node_id in candidate_node_ids:
                if node_id in line:
                    selected_ids.append(node_id)
        elif "주제" in line:
            new_topic = line.split(':')[-1].strip()
    
    return selected_ids[:fanout_limit-1], new_topic # fanout_limit-1개까지만 선택, 인공지능이 잘못 출력했을 수 도 있으므로

# 대화 요약 AI
def summary_AI(conversation_data: list, max_length: int = 200) -> str:
    """
    대화 데이터를 지정된 길이로 요약
    """
    system_prompt = f"""다음 대화를 {max_length}자 이내로 간결하게 요약해라. 핵심 내용만 포함해라."""
    
    prompt = "대화 내용:\n"
    for msg in conversation_data:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        prompt += f"{role}: {content}\n"
    
    debug_print(f"요약 생성 중 (대화 수: {len(conversation_data)}개, 목표 길이: {max_length}자)")
    result = AI(prompt, system_prompt)
    debug_print(f"요약 생성 완료 (실제 길이: {len(result)}자)")
    return result.strip()

# 주제명 생성 AI
def topic_generation_AI(summary_data: str) -> str:
    """
    요약 데이터를 바탕으로 적절한 주제명 생성
    """
    system_prompt = """주어진 요약 내용을 보고 핵심 주제를 파악하여 간결한 주제명을 생성해라.
주제명은 다음 규칙을 따라라:
1. 5-8자의 명사형 구문으로 작성
2. 구체적이고 명확한 내용으로 작성 (예: "과학 상식", "수학 공식", "개인 정보")
3. 너무 추상적이거나 포괄적이지 않게 작성
4. 마크다운 형식 사용 금지
5. 한국어로 작성

예시:
- "물리학 기초 개념" (O)
- "화학 원소 정보" (O)  
- "수학 정리 설명" (O)
- "일반적인 대화" (X - 너무 포괄적)
- "인사말" (X - 너무 포괄적)

주제명만 출력하세요."""
    
    prompt = f"요약 내용: {summary_data}"
    
    debug_print("주제 생성 중...")
    result = AI(prompt, system_prompt)
    # 마크다운 형식 제거
    result = result.strip().replace('**', '').replace('*', '').replace('#', '')
    debug_print(f"주제 생성 완료: '{result}'")
    return result.strip()

# 부모 노드 업데이트 AI
def parent_update_AI(old_summary: str, new_content: str, max_length: int = 300) -> tuple:
    """
    부모 노드의 요약을 압축하여 업데이트
    """
    system_prompt = f"""기존 요약과 새로운 내용을 통합하여 {max_length}자 이내의 새로운 요약과 업데이트된 주제명을 생성해라.

출력 형식:
새 요약: [요약 내용]
새 주제명: [주제명]"""
    
    prompt = f"기존 요약: {old_summary}\n새로운 내용: {new_content}"
    
    result = AI(prompt, system_prompt)
    
    # 결과 파싱
    lines = result.split('\n')
    new_summary = old_summary  # 기본값
    new_topic = "업데이트된 주제"  # 기본값
    
    for line in lines:
        if "요약" in line and ":" in line:
            new_summary = line.split(':', 1)[-1].strip()
        elif "주제" in line and ":" in line:
            new_topic = line.split(':', 1)[-1].strip()
    
    return new_summary, new_topic
