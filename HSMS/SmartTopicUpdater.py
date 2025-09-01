import re
import asyncio
from config import TOPIC_UPDATE_FINE_SHOTS, CATEGORY_PLACEMENT_FINE_SHOTS, TOPIC_GENERATION_FINE_SHOTS


class SmartTopicUpdater:
    """스마트 토픽 업데이트 시스템 - Few-Shot 학습 기반 지능적 주제명 갱신"""
    
    def __init__(self, ai_manager, similarity_threshold=0.7, debug=False, update_mode='smart'):
        self.ai_manager = ai_manager
        self.similarity_threshold = similarity_threshold
        self.debug = debug
        self.update_mode = update_mode  # 'always', 'smart', 'never'
        self.update_stats = {
            'evaluations': 0,
            'updates_performed': 0,
            'categories_created': 0,
            'forced_placements_prevented': 0,
            'depth_exceeded_warnings': 0
        }

    async def should_update_topic(self, node, new_conversation_content):
        """AI few-shot 학습을 사용하여 토픽 업데이트 필요성 판단"""
        self.update_stats['evaluations'] += 1
        
        if self.debug:
            print(f"  ┌─ [SMART-TOPIC] 업데이트 필요성 평가")
            print(f"  │  현재 주제: '{node.topic}'")
            print(f"  │  업데이트 모드: {self.update_mode}")
            print(f"  │  임계값: {self.similarity_threshold}")

        # 업데이트 모드별 처리
        if self.update_mode == 'never':
            if self.debug:
                print(f"  │  결과: 업데이트 비활성화 모드")
                print(f"  └─ 평가 완료 (업데이트 안함)")
            return False, 1.0
        
        if self.update_mode == 'always':
            if self.debug:
                print(f"  │  결과: 항상 업데이트 모드")
                print(f"  └─ 평가 완료 (항상 업데이트)")
            return True, 0.0

        # Smart 모드: AI 기반 판단
        if self.debug:
            print(f"  │  AI 기반 판단 시작...")

        # Few-shot 예시 구성
        few_shot_examples = ""
        for i, (example, expected_score) in enumerate(TOPIC_UPDATE_FINE_SHOTS, 1):
            few_shot_examples += f"""
=== 예시 {i} ===
{example}

점수: {expected_score}
판단: {'업데이트 필요' if float(expected_score) < self.similarity_threshold else '업데이트 불필요'}
---
"""

        # 현재 상황에 대한 프롬프트
        current_prompt = f"""현재 노드 정보:
- 주제: {node.topic}
- 요약: {node.summary[:200]}{'...' if len(node.summary) > 200 else ''}

새로 추가될 내용:
{new_conversation_content[:300]}{'...' if len(new_conversation_content) > 300 else ''}

새로운 내용이 기존 주제와 얼마나 일치하는지 0-1 점수로 평가하라.
평가 기준:
- 0.7 이상: 주제가 잘 맞음 (업데이트 불필요)
- 0.3-0.7: 주제 확장 필요 (부분 업데이트)
- 0.3 미만: 주제가 맞지 않음 (업데이트 필요)

현재 임계값: {self.similarity_threshold} (이 값 미만이면 업데이트)

점수만 출력하라."""

        system_prompt = f"""당신은 토픽 일치도를 평가하는 AI입니다. 아래 예시들을 참고하여 정확하게 판단하세요.

{few_shot_examples}

위 예시들을 참고하여 현재 상황을 평가하세요."""

        try:
            if self.debug:
                print(f"  │  AI 호출 중... (few-shot 예시 {len(TOPIC_UPDATE_FINE_SHOTS)}개 사용)")
            
            result = await self.ai_manager.call_ai_async_single(
                current_prompt, system_prompt, suppress_individual_debug=True
            )
            
            if self.debug:
                print(f"  │  AI 응답: '{result.strip()}'")
            
            # 점수 추출
            match = re.search(r'(\d+\.?\d*)', result.strip())
            if match:
                score = float(match.group(1))
                score = max(0.0, min(1.0, score))  # 0-1 범위 제한
            else:
                score = 0.5  # 기본값
                if self.debug:
                    print(f"  │  점수 추출 실패, 기본값 사용: {score}")
            
            should_update = score < self.similarity_threshold
            
            if self.debug:
                print(f"  │  일치도 점수: {score:.3f}")
                print(f"  │  임계값: {self.similarity_threshold}")
                print(f"  │  업데이트 필요: {'예' if should_update else '아니오'}")
                if should_update:
                    print(f"  │  이유: 점수({score:.3f}) < 임계값({self.similarity_threshold})")
                else:
                    print(f"  │  이유: 점수({score:.3f}) >= 임계값({self.similarity_threshold})")
                print(f"  └─ 평가 완료")
            
            return should_update, score
            
        except Exception as e:
            if self.debug:
                print(f"  │  오류 발생: {e}")
                print(f"  │  기본값 반환 (업데이트 안함)")
                print(f"  └─ 평가 완료 (오류로 인한 기본값)")
            return False, 0.8

    async def should_create_new_category(self, existing_categories, new_conversation):
        """새 카테고리 생성 필요성 판단 (fanout-limit 고려)"""
        if self.debug:
            print(f"  ┌─ [SMART-TOPIC] 새 카테고리 생성 필요성 평가")

        # Few-shot 예시 구성
        few_shot_examples = ""
        for example, expected_decision in CATEGORY_PLACEMENT_FINE_SHOTS:
            few_shot_examples += f"""
예시:
{example}

결정: {expected_decision}
---
"""

        # 기존 카테고리 정보 구성
        category_info = ""
        for i, (name, info) in enumerate(existing_categories.items(), 1):
            category_info += f"{i}. {name} ({info.get('summary', '')[:50]}...)\n"

        current_prompt = f"""기존 카테고리들:
{category_info}

새로운 대화:
{new_conversation}

판단: 이 새로운 대화가 기존 카테고리 중 어디에 속하는지, 아니면 새로운 카테고리가 필요한지 판단하라.

기존 카테고리에 적합하면 해당 카테고리명을 출력하고,
새 카테고리가 필요하면 "NEW_CATEGORY"를 출력하라."""

        system_prompt = f"""당신은 카테고리 분류를 담당하는 AI입니다. 아래 예시들을 참고하여 정확하게 판단하세요.

{few_shot_examples}

위 예시들을 참고하여 현재 상황을 판단하세요."""

        try:
            result = await self.ai_manager.call_ai_async_single(
                current_prompt, system_prompt, suppress_individual_debug=True
            )
            
            result = result.strip()
            needs_new_category = result == "NEW_CATEGORY"
            target_category = None if needs_new_category else result
            
            if self.debug:
                if needs_new_category:
                    print(f"  │  결정: 새 카테고리 생성 필요")
                    self.update_stats['categories_created'] += 1
                else:
                    print(f"  │  결정: '{target_category}' 카테고리에 배치")
                print(f"  └─ 카테고리 배치 결정 완료")
            
            return needs_new_category, target_category
            
        except Exception as e:
            if self.debug:
                print(f"  │  오류 발생: {e}")
                print(f"  └─ 기본값 반환 (새 카테고리 생성)")
            return True, None

    async def generate_updated_topic(self, node, child_summaries):
        """Few-shot 학습을 사용한 개선된 주제명 생성"""
        if self.debug:
            print(f"  ┌─ [SMART-TOPIC] 주제명 생성")
            print(f"  │  기존 주제: {node.topic}")

        # Few-shot 예시 구성
        few_shot_examples = ""
        for example, expected_topic in TOPIC_GENERATION_FINE_SHOTS:
            few_shot_examples += f"""
예시:
{example}
"{expected_topic}"
---
"""

        child_topics = [summary.split(':')[0] if ':' in summary else summary[:20] 
                       for summary in child_summaries[:5]]  # 최대 5개만

        current_prompt = f"""기존 주제: {node.topic}
자식 노드들: {', '.join(child_topics)}

이 노드의 새로운 주제를 생성하라.
조건:
- 2-8자 이내의 명사
- 자식 노드들의 공통된 주제를 포괄
- 구체적이면서도 포용적인 이름
- 따옴표 안에 답변

새로운 주제를 생성하라 (2-8자 명사):"""

        system_prompt = f"""당신은 카테고리 주제명을 생성하는 AI입니다. 아래 예시들을 참고하여 적절한 주제명을 만드세요.

{few_shot_examples}

위 예시들을 참고하여 현재 상황에 맞는 주제명을 생성하세요."""

        try:
            result = await self.ai_manager.call_ai_async_single(
                current_prompt, system_prompt, suppress_individual_debug=True
            )
            
            # 따옴표 안의 내용 추출
            match = re.search(r'"([^"]{2,8})"', result)
            if match:
                new_topic = match.group(1).strip()
            else:
                # 따옴표가 없으면 첫 번째 단어 추출
                words = result.strip().split()
                new_topic = words[0] if words else node.topic
            
            # 길이 제한 확인
            if len(new_topic) > 8:
                new_topic = new_topic[:8]
            elif len(new_topic) < 2:
                new_topic = node.topic
            
            if self.debug:
                print(f"  │  새 주제: {new_topic}")
                print(f"  └─ 주제명 생성 완료")
            
            self.update_stats['updates_performed'] += 1
            return new_topic
            
        except Exception as e:
            if self.debug:
                print(f"  │  오류 발생: {e}")
                print(f"  └─ 기존 주제 유지")
            return node.topic

    async def handle_fanout_overflow_smart(self, parent_node, new_conversation, existing_categories, fanout_limit, current_depth=0, max_depth=10, flexible_depth=False):
        """스마트한 fanout 오버플로우 처리 (절대 fanout-limit 초과 금지)"""
        if self.debug:
            print(f"  ┌─ [SMART-TOPIC] Fanout 오버플로우 처리")
            print(f"  │  부모 노드: '{parent_node.topic}'")
            print(f"  │  현재 자식 수: {len(parent_node.children_ids)}")
            print(f"  │  Fanout 제한: {fanout_limit}")
            print(f"  │  현재 깊이: {current_depth}")
            print(f"  │  최대 깊이: {max_depth}")
            print(f"  │  깊이 유연성: {'허용' if flexible_depth else '제한'}")

        # 현재 fanout이 한계에 도달했는지 확인 (fanout_limit개까지 허용)
        fanout_exceeded = len(parent_node.children_ids) > fanout_limit  # 실제 초과
        depth_exceeded = current_depth >= max_depth
        
        if self.debug:
            print(f"  │  fanout 상태: {len(parent_node.children_ids)}/{fanout_limit} ({'초과' if fanout_exceeded else '허용'})")
            print(f"  │  깊이 상태: {current_depth}/{max_depth} ({'초과' if depth_exceeded else '허용'})")
        
        if fanout_exceeded and depth_exceeded and not flexible_depth:
            # 둘 다 최대이고 flexible_depth가 False인 경우
            if self.debug:
                print(f"  │  ⚠️  CRITICAL: Fanout({len(parent_node.children_ids)}>={fanout_limit}) AND Depth({current_depth}>={max_depth}) 모두 한계")
                print(f"  │  ⚠️  flexible-depth 비활성화 상태")
                print(f"  │  ⚠️  경고: max-depth를 강제로 초과합니다")
            
            self.update_stats['depth_exceeded_warnings'] += 1
            
            # 경고 메시지 출력
            print(f"\n⚠️  [경고] 트리 구조 한계 도달!")
            print(f"   - Fanout 한계: {len(parent_node.children_ids)}/{fanout_limit}")
            print(f"   - 깊이 한계: {current_depth}/{max_depth}")
            print(f"   - 대처: max-depth를 초과하여 새 카테고리 생성")
            print(f"   - 권장: --flexible-depth 옵션 사용 고려\n")
            
            # 강제로 새 카테고리 생성 (depth 초과)
            if self.debug:
                print(f"  │  결정: 깊이 제한 무시하고 새 카테고리 생성")
                print(f"  └─ 강제 깊이 초과 처리 완료")
            
            return True, None  # 새 카테고리 생성
        
        elif fanout_exceeded:
            if self.debug:
                print(f"  │  Fanout 한계 도달: 기존 카테고리에 배치 필요")
            
            # 새 카테고리 생성 불가, 기존 카테고리 중 최적 선택
            needs_new, target_category = await self.should_create_new_category(
                existing_categories, new_conversation
            )
            
            if needs_new:
                # 새 카테고리가 필요하지만 생성할 수 없음
                if self.debug:
                    print(f"  │  새 카테고리 필요하지만 fanout 한계로 인해 강제 배치")
                self.update_stats['forced_placements_prevented'] += 1
                
                # 가장 관련성 높은 기존 카테고리 선택
                best_category = await self._find_best_existing_category(
                    existing_categories, new_conversation
                )
                
                if self.debug:
                    print(f"  │  최적 기존 카테고리: '{best_category}'")
                    print(f"  └─ 강제 배치 완료 (토픽 업데이트 예정)")
                
                return False, best_category  # 새 카테고리 생성 안함, 기존 카테고리 반환
            else:
                # 기존 카테고리에 적합함
                if self.debug:
                    print(f"  │  기존 카테고리 '{target_category}'에 적합")
                    print(f"  └─ 정상 배치")
                
                return False, target_category
        else:
            # 아직 fanout 여유가 있음
            needs_new, target_category = await self.should_create_new_category(
                existing_categories, new_conversation
            )
            
            if needs_new:
                if depth_exceeded and not flexible_depth:
                    # 깊이 제한에 걸렸지만 fanout은 여유 있음
                    if self.debug:
                        print(f"  │  새 카테고리 필요하지만 깊이 제한({current_depth}>={max_depth})")
                        print(f"  │  flexible-depth 비활성화로 기존 카테고리에 배치")
                    
                    best_category = await self._find_best_existing_category(
                        existing_categories, new_conversation
                    )
                    return False, best_category
                else:
                    if self.debug:
                        print(f"  │  새 카테고리 생성 가능")
                        if depth_exceeded and flexible_depth:
                            print(f"  │  깊이 초과하지만 flexible-depth로 허용")
                        print(f"  └─ 새 카테고리 생성")
                    return True, None  # 새 카테고리 생성
            else:
                if self.debug:
                    print(f"  │  기존 카테고리 '{target_category}'에 배치")
                    print(f"  └─ 기존 카테고리 사용")
                return False, target_category

    async def _find_best_existing_category(self, existing_categories, new_conversation):
        """기존 카테고리 중 가장 적합한 것 선택"""
        best_category = None
        best_score = -1
        
        for category_name, category_info in existing_categories.items():
            prompt = f"""
            카테고리: {category_name}
            카테고리 요약: {category_info.get('summary', '')}
            
            새로운 대화:
            {new_conversation}
            
            이 새로운 대화가 해당 카테고리에 얼마나 적합한지 0-1 점수로 평가하라.
            점수만 출력하라.
            """
            
            try:
                result = await self.ai_manager.call_ai_async_single(
                    prompt, "카테고리 적합성 평가", suppress_individual_debug=True
                )
                score = float(re.search(r'(\d+\.?\d*)', result.strip()).group(1))
                
                if score > best_score:
                    best_score = score
                    best_category = category_name
                    
            except Exception:
                continue
        
        return best_category or list(existing_categories.keys())[0]  # 실패 시 첫 번째 카테고리

    def get_update_statistics(self):
        """업데이트 통계 반환"""
        return self.update_stats.copy()

    def reset_statistics(self):
        """통계 초기화"""
        self.update_stats = {
            'evaluations': 0,
            'updates_performed': 0,
            'categories_created': 0,
            'forced_placements_prevented': 0,
            'depth_exceeded_warnings': 0
        }
