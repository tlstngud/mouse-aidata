"""
GRPO Reward Configuration

보상 체계 설정:
- 게임 점수 기반 (정규화)
- 프로그램 구조 보너스
- 탐험 보상 (선택적)
"""

from dataclasses import dataclass


@dataclass
class RewardConfig:
    """GRPO 보상 설정"""

    # === 게임 점수 정규화 (이벤트별 분리!) ===
    game_score_scale: float = 0.1  # 기본 스케일 (fallback)

    # ⭐ 치즈 보상 강화 (0.1 → 0.5, 5배 증가)
    cheese_reward_scale: float = 0.5  # 작은 치즈 +10 → +5.0, 큰 치즈 +500 → +250.0

    # ⭐ 벽 패널티 강화 (0.1 → 0.3, 3배 증가)
    wall_penalty_scale: float = 0.3  # 벽 충돌 -10 → -3.0

    # 고양이는 나중에 (현재 낮게 유지)
    cat_penalty_scale: float = 0.05  # 고양이 충돌 -500 → -25.0 (낮게 유지)

    # === 프로그램 구조 보상 ===
    end_token: float = 0.0           # END 토큰 - 중립 (보상 없음)
    end_missing: float = -2.0        # END 토큰 없음 패널티 (강화)
    loop_complete: float = 1.0       # LOOP 구조 완성 (110+N+D)
    if_complete: float = 0.1         # IF 구조 완성 - 낮게 유지 (고양이 회피는 나중에)
    grammar_violation: float = -3.0  # 문법 위반
    incomplete_structure: float = -2.0  # 구조 미완성
    inefficient_pattern: float = -0.5   # 비효율 패턴 (좌→우→좌)

    # === 탐험 보상 (선택적) ===
    new_cell: float = 0.1            # 새로운 칸 방문
    cat_escape: float = 0.3          # 고양이 회피 성공

    # === 토큰 길이 보상 (강화) ===
    length_bonus_per_token: float = 0.3   # 토큰당 보너스 (0.15→0.3, 2배 증가)
    length_bonus_max: int = 10            # 최대 보상 토큰 수 (10토큰 × 0.3 = 3.0)
    short_program_penalty: float = -4.0   # 3토큰 이하 패널티 (강화: -3.0 → -4.0)

    # === 하이퍼파라미터 ===
    gamma: float = 0.95              # 할인율
    epsilon: float = 0.1             # advantage 정규화 epsilon
    min_std: float = 0.5             # 최소 표준편차

    # === 토큰 ID 상수 ===
    END_TOKEN: int = 112
    LOOP_TOKEN: int = 110
    IF_TOKEN: int = 5
    DIRECTIONS: tuple = (0, 1, 2, 3)
    NUMBERS: tuple = tuple(range(100, 110))


def compute_length_bonus(program: list, config: RewardConfig = None) -> float:
    """
    프로그램 길이에 대한 보상 계산

    Args:
        program: 프로그램 토큰 리스트
        config: RewardConfig 인스턴스

    Returns:
        length_bonus: 길이 보상 값

    보상 체계:
        - END 토큰(112) 제외하고 계산
        - 실제 명령어 2개 이하: 패널티 (-1.0)
        - 실제 명령어 3~10개: 토큰당 +0.15
        - 최대 보상: 10 × 0.15 = 1.5

    게임 규칙:
        - 게임은 최대 10개 명령어 허용 (END 없음)
        - 학습 데이터는 명령어 + END = 최대 11토큰
    """
    if config is None:
        config = RewardConfig()

    # END 토큰(112) 제외하고 실제 명령어 수 계산
    actual_commands = len(program)
    if len(program) > 0 and program[-1] == config.END_TOKEN:
        actual_commands -= 1  # END 제외

    # 너무 짧은 프로그램 패널티 (실제 명령어 2개 이하)
    if actual_commands <= 2:
        return config.short_program_penalty

    # 길이 보상 (최대 10개 명령어까지)
    effective_length = min(actual_commands, config.length_bonus_max)
    length_bonus = effective_length * config.length_bonus_per_token

    return length_bonus


def compute_structure_reward(program: list, config: RewardConfig = None) -> float:
    """
    프로그램 구조에 대한 보상 계산

    Args:
        program: 프로그램 토큰 리스트
        config: RewardConfig 인스턴스

    Returns:
        structure_reward: 구조 보상 값
    """
    if config is None:
        config = RewardConfig()

    reward = 0.0

    # 0. 길이 보상 추가
    reward += compute_length_bonus(program, config)

    # 1. END 토큰 체크
    if len(program) > 0 and program[-1] == config.END_TOKEN:
        reward += config.end_token
    else:
        reward += config.end_missing

    # 2. LOOP/IF 구조 체크
    i = 0
    while i < len(program):
        token = program[i]

        if token == config.LOOP_TOKEN or token == config.IF_TOKEN:
            # 3토큰 구조 검증 (LOOP/IF + NUM + DIR)
            if i + 2 < len(program):
                num_token = program[i + 1]
                dir_token = program[i + 2]

                if num_token in config.NUMBERS and dir_token in config.DIRECTIONS:
                    # 완전한 구조
                    if token == config.LOOP_TOKEN:
                        reward += config.loop_complete
                    else:
                        reward += config.if_complete
                else:
                    # 문법 위반
                    reward += config.grammar_violation
            else:
                # 구조 미완성
                reward += config.incomplete_structure
            i += 3
        else:
            i += 1

    # 3. 비효율 패턴 체크 (좌→우→좌, 상→하→상 등)
    directions = [t for t in program if t in config.DIRECTIONS]
    opposing_pairs = {(0, 1), (1, 0), (2, 3), (3, 2)}

    for j in range(len(directions) - 2):
        if directions[j] == directions[j + 2]:
            pair = (directions[j], directions[j + 1])
            if pair in opposing_pairs:
                reward += config.inefficient_pattern

    return reward


def compute_total_reward(
    game_score_delta: float,
    program: list,
    config: RewardConfig = None
) -> float:
    """
    총 보상 계산

    Args:
        game_score_delta: run 전후 게임 점수 변화
        program: 프로그램 토큰 리스트
        config: RewardConfig 인스턴스

    Returns:
        total_reward: 최종 보상 값
    """
    if config is None:
        config = RewardConfig()

    # 1. 게임 점수 정규화
    game_reward = game_score_delta * config.game_score_scale

    # 2. 구조 보상
    structure_reward = compute_structure_reward(program, config)

    # 3. 총합
    total_reward = game_reward + structure_reward

    return total_reward


# 테스트
if __name__ == "__main__":
    print("=" * 60)
    print("RewardConfig 테스트")
    print("=" * 60)

    config = RewardConfig()

    # 테스트 프로그램들
    # END(112) 포함된 형태로 테스트 (실제 학습 데이터 형식)
    test_cases = [
        # (프로그램, 게임 점수 변화, 설명)
        ([0, 112], 10, "1명령어+END (너무 짧음)"),
        ([0, 0, 112], 15, "2명령어+END (너무 짧음)"),
        ([0, 0, 0, 112], 20, "3명령어+END (최소)"),
        ([110, 103, 2, 112], 30, "3명령어+END (LOOP)"),
        ([0, 0, 0, 0, 0, 112], 25, "5명령어+END"),
        ([110, 103, 2, 0, 1, 2, 3, 112], 40, "7명령어+END"),
        ([0, 1, 2, 3, 0, 1, 2, 3, 0, 112], 50, "9명령어+END"),
        ([0, 1, 2, 3, 0, 1, 2, 3, 0, 3, 112], 60, "10명령어+END (최대)"),
    ]

    for program, score_delta, desc in test_cases:
        total = compute_total_reward(score_delta, program, config)
        structure = compute_structure_reward(program, config)
        length = compute_length_bonus(program, config)
        game = score_delta * config.game_score_scale

        # 실제 명령어 수 (END 제외)
        actual_cmds = len(program) - 1 if program[-1] == 112 else len(program)

        print(f"\n{desc}")
        print(f"  Program: {program}")
        print(f"  토큰 수: {len(program)} (실제 명령어: {actual_cmds}개)")
        print(f"  Game reward: {game:.2f}")
        print(f"  Length bonus: {length:.2f}")
        print(f"  Structure reward: {structure:.2f}")
        print(f"  Total reward: {total:.2f}")

    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)
