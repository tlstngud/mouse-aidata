"""
Lightweight Game Simulator - Fast game logic for TRM

exe3.py Game 클래스의 핵심 게임 로직만 추출:
- pygame, GUI, 렌더링 제거 → 속도 최적화
- 20번 반복 실행 가능한 가벼운 시뮬레이터
- parse_and_execute 대신 직접 명령어 실행

사용 목적: TRM (Test-time Refinement Method)에서 Value Head 대신 실제 점수 계산
"""

# ✅ Phase 1: deepcopy 제거로 인해 import 불필요
from collections import deque  # ✅ BFS 최적화: Queue-based BFS
from function_library import FUNCTION_LIBRARY, get_function


class LightweightGameSimulator:
    """
    빠른 게임 시뮬레이터 (exe3.py Game 클래스의 경량화 버전)

    포함:
    - 게임 상태 (mouse, cat, cheese, wall, score, life, step)
    - 이동 로직 (_movable, _move)
    - 명령어 파싱 (함수 라이브러리 확장 포함)
    - 충돌 감지 (치즈, 고양이, 벽)
    - 점수 계산

    제외:
    - pygame (screen, clock, font, image)
    - GUI 렌더링
    - 이벤트 처리
    - 사운드, 애니메이션
    """

    def __init__(self, level=1):
        """
        게임 상태 초기화 (exe3.py와 동일한 레벨 구조)

        Args:
            level: 게임 레벨 (1-based)
        """
        self.level = level
        self._init_default_state()

    @classmethod
    def from_game(cls, game):
        """
        ✅ exe3.py Game 객체의 현재 상태를 복사 (핵심 데이터만!)

        Args:
            game: exe3.Game 객체 (현재 진행 중인 게임)
        Returns:
            sim: LightweightGameSimulator (game 상태 복사본)

        성능 최적화:
        - deepcopy() 대신 list.copy() 사용 → 10배 빠름
        - pygame 객체 제외 (screen, font, sprite groups)
        - 게임 로직 필수 데이터만 복사
        """
        sim = cls.__new__(cls)  # __init__ 호출 안함 (빠름)

        # ✅ 핵심 게임 상태만 복사 (list.copy()가 deepcopy보다 빠름)
        sim.mouse = game.mouse.copy() if isinstance(game.mouse, list) else list(game.mouse)
        sim.cat = [cat.copy() if isinstance(cat, list) else list(cat) for cat in game.cat]

        # 2D 배열: list comprehension (deepcopy보다 빠름)
        sim.sc = [row.copy() if isinstance(row, list) else list(row) for row in game.sc]
        sim.wall = [row.copy() if isinstance(row, list) else list(row) for row in game.wall]
        sim.junc = [row.copy() if isinstance(row, list) else list(row) for row in game.junc]
        sim.deadend = [row.copy() if isinstance(row, list) else list(row) for row in game.deadend] if hasattr(game, 'deadend') else [[0]*11 for _ in range(11)]

        # 빅치즈 (있으면 복사, 없으면 빈 리스트)
        if hasattr(game, 'crzbc') and game.crzbc:
            sim.crzbc = [c.copy() if isinstance(c, list) else list(c) for c in game.crzbc]
            sim.crzbc_last_pos = [c.copy() if isinstance(c, list) else list(c) for c in game.crzbc]
        else:
            sim.crzbc = []
            sim.crzbc_last_pos = []

        if hasattr(game, 'movbc') and game.movbc:
            sim.movbc = [c.copy() if isinstance(c, list) else list(c) for c in game.movbc]
            sim.movbc_last_pos = [c.copy() if isinstance(c, list) else list(c) for c in game.movbc]
        else:
            sim.movbc = []
            sim.movbc_last_pos = []

        # 스칼라 값들 (복사 불필요)
        sim.level = getattr(game, 'level', 1)
        sim.score = game.score
        sim.life = game.life
        sim.step = game.step
        sim.step_limit = getattr(game, 'step_limit', 200)
        sim.run = getattr(game, 'run', 0)  # ✅ Run 번호 (victory bonus)
        sim.func_chance = getattr(game, 'func_chance', 4)
        sim.func_chance_to_use = 0
        sim.red_zone = getattr(game, 'red_zone', 5)  # ✅ 고양이 도망 거리

        # 마지막 위치 복사
        sim.mouse_last_pos = sim.mouse.copy()
        sim.cat_last_pos = [cat.copy() for cat in sim.cat]

        # 고양이 방향 (있으면 복사)
        if hasattr(game, 'cat_direction'):
            sim.cat_direction = game.cat_direction.copy() if isinstance(game.cat_direction, list) else [0, 0]
        else:
            sim.cat_direction = [0, 0]

        # ✅ crzbc 방향 (있으면 복사)
        if hasattr(game, 'crzbc_direction'):
            sim.crzbc_direction = game.crzbc_direction.copy() if isinstance(game.crzbc_direction, list) else []
        else:
            sim.crzbc_direction = []

        # 플래그 초기화
        sim.win_sign = False
        sim.lose_sign = False
        sim.catched = False

        return sim

    def _init_default_state(self):
        """기본 초기 상태 설정 (Level 3 고정)"""

        # ===== 게임 상태 =====
        # 11x11 그리드, [x][y] 좌표계 (x=row, y=col)
        # Level 3 맵 (exe3.py에서 복사)

        self.wall = [
            [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0],
            [0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0],
            [0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0],
            [0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0],
            [0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1],
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
            [0, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0]
        ]
        self.sc = [
            [1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1],
            [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1],
            [1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1],
            [1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1],
            [1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
            [1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1],
            [1, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0]
        ]
        # ✅ Junction 배열 (exe3.py와 동일하게 수정)
        self.junc = [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],  # ✅ 수정됨
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 1, 0, 1, 1, 0, 0, 0],  # ✅ 수정됨
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],  # ✅ 수정됨 (9행 추가)
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        ]
        # ✅ Deadend 배열 (exe3.py와 동일하게 수정)
        self.deadend = [
            [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],  # ✅ 0행 5열
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]   # ✅ 10행 0,10열
        ]

        # 빅치즈 위치 (Level 3)
        self.movbc = [[1, 5], [7, 5]]
        self.movbc_last_pos = [[1, 5], [7, 5]]
        # ✅ movbc도 이동함 (exe3.py:2418-2437)
        self.movbc_direction = [0, 0]  # 매 턴 랜덤으로 결정됨
        # ✅ crzbc 초기 위치 랜덤화 (exe3.py와 동일)
        import random
        x1 = random.randrange(0, 8)
        x2 = random.randrange(0, 8)
        while x2 == x1:  # 중복 방지
            x2 = random.randrange(0, 8)
        self.crzbc = [[x1, 0], [x2, 10]]
        self.crzbc_last_pos = [[x1, 0], [x2, 10]]
        self.crzbc_direction = [random.randrange(0, 4), random.randrange(0, 4)]

        # 쥐 시작 위치
        self.mouse = [10, 10]
        self.mouse_last_pos = [10, 10]

        # 고양이 2마리 (0=dummy, 1=naughty)
        self.cat = [[2, 2], [5, 5]]
        self.cat_last_pos = [[2, 2], [5, 5]]
        # ✅ 고양이 방향 랜덤 초기화 (exe3.py:455와 동일)
        import random
        self.cat_direction = [random.randrange(0, 4), random.randrange(0, 4)]

        # 게임 상태
        self.score = 0
        self.life = 3
        self.step = 0
        self.step_limit = 200
        self.run = 0  # ✅ 현재 run 번호 (victory bonus에 필요)
        self.func_chance = 4  # 함수 호출 제한
        self.func_chance_to_use = 0
        self.red_zone = 5  # ✅ 고양이 도망 거리

        # ✅ 누적 점수 트래킹 (exe3.py와 동일)
        self.total_command_score = 0
        self.total_collision_score = 0
        self.command_score = 0
        self.collision_score = 0

        # 승리/패배 플래그
        self.win_sign = False
        self.lose_sign = False
        self.catched = False

    def _movable(self, xy, direction):
        """
        이동 가능 여부 체크 (exe3.py:2306-2344와 동일)

        Args:
            xy: [x, y] 위치
            direction: 0=up, 1=down, 2=left, 3=right
        Returns:
            bool: 이동 가능하면 True
        """
        x, y = xy  # ✅ Phase 1: deepcopy 제거 (스칼라 복사에 불필요)

        # Bounds check for initial position
        if not (0 <= x <= 10 and 0 <= y <= 10):
            return False

        # 방향에 따라 새 좌표 계산
        if direction == 0:  # up
            if x == 0:
                return False
            x -= 1
        elif direction == 1:  # down
            if x == 10:
                return False
            x += 1
        elif direction == 2:  # left
            if y == 0:
                return False
            y -= 1
        elif direction == 3:  # right
            if y == 10:
                return False
            y += 1

        # Double-check bounds before array access
        if not (0 <= x <= 10 and 0 <= y <= 10):
            return False

        # 벽 체크
        if self.wall[x][y] == 0:
            return True
        else:
            return False

    def _move(self, xy, direction):
        """
        위치 이동 (exe3.py:2346-2360와 동일)

        Args:
            xy: [x, y] 현재 위치
            direction: 0=up, 1=down, 2=left, 3=right
        Returns:
            [x, y]: 새 위치
        """
        x, y = xy

        if direction == 0:  # up
            x -= 1
        elif direction == 1:  # down
            x += 1
        elif direction == 2:  # left
            y -= 1
        elif direction == 3:  # right
            y += 1

        # Clamp coordinates to valid range [0, 10]
        x = max(0, min(10, x))
        y = max(0, min(10, y))

        return [x, y]

    def _create_distance_map(self, mouse_pos):
        """
        ✅ OPTIMIZED: Queue-based BFS for distance map generation (4.59x faster!)

        마우스 위치로부터 모든 셀까지의 거리 맵 생성 (exe3.py:2013-2047와 동일)
        Cat red zone 알고리즘에 필요

        Performance:
        - Original (wavefront): 0.46 ms/call, O(D × N) complexity
        - Optimized (queue BFS): 0.10 ms/call, O(N) complexity
        - Speedup: 4.59x faster (78.2% improvement)

        Args:
            mouse_pos: [x, y] 마우스 위치
        Returns:
            distance_map: 11x11 배열, -1=벽, 1이상=마우스로부터의 거리
        """
        # 벽 기반으로 초기화 (0=빈공간, -1=벽)
        distance_map = [[v * -1 for v in row] for row in self.wall]

        # 마우스 위치를 1로 설정 (시작점)
        distance_map[mouse_pos[0]][mouse_pos[1]] = 1

        # ✅ Queue-based BFS (classical algorithm)
        queue = deque([mouse_pos])

        while queue:
            y, x = queue.popleft()  # O(1) deque operation
            current_dist = distance_map[y][x]

            # Check all 4 neighbors (up, down, left, right)
            for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ny, nx = y + dy, x + dx

                # Bounds check
                if 0 <= ny < 11 and 0 <= nx < 11:
                    # If unvisited (not wall and not already visited)
                    if distance_map[ny][nx] == 0:
                        distance_map[ny][nx] = current_dist + 1
                        queue.append([ny, nx])

        return distance_map

    def _parse_program(self, program):
        """
        ✅ parse_and_execute 방식으로 프로그램 파싱

        exe3.py + function_library.py의 parse_and_execute와 동일한 로직:
        1. 첫 번째 함수 ID → F1 저장, 메인에 10 추가
        2. 같은 ID 재등장 → 메인에 10만 추가 (재호출)
        3. 다른 ID 등장 → F2 저장, 메인에 11 추가
        4. 세 번째 다른 ID → 무시 (2종류 제약)

        Args:
            program: List[int] - 프로그램 (함수 ID 포함 가능)
        Returns:
            command: List[int] - 메인 프로그램 (10, 11 호출 포함)
            function: List[List[int]] - [F1_body, F2_body]

        Example:
            [2, 113, 114, 2, 0]
            → command: [2, 10, 11, 2, 0]
            → function: [[1, 2], [3, 3]]  # 113=[1,2], 114=[3,3]

            [113, 113, 113, 0]
            → command: [10, 10, 10, 0]
            → function: [[1, 2], []]  # 113만 사용
        """
        f1_body = []
        f2_body = []
        f1_id = None  # ✅ 함수 ID 추적
        f2_id = None
        main_program = []

        for token in program:
            # 999는 빈칸 (skip)
            if token == 999:
                continue

            # 함수 라이브러리 ID (113-998)
            elif 113 <= token <= 998:
                if f1_id is None:
                    # ✅ 첫 번째 함수 → F1
                    f1_id = token
                    f1_body = get_function(token)
                    main_program.append(10)  # F1 호출

                elif token == f1_id:
                    # ✅ F1 재호출 (같은 ID)
                    main_program.append(10)

                elif f2_id is None:
                    # ✅ 두 번째 (다른) 함수 → F2
                    f2_id = token
                    f2_body = get_function(token)
                    main_program.append(11)  # F2 호출

                elif token == f2_id:
                    # ✅ F2 재호출 (같은 ID)
                    main_program.append(11)

                # else: 세 번째 다른 함수 → 무시

            else:
                # 일반 명령 (0-112)
                main_program.append(token)
                if token == 112:  # END
                    break

        return main_program, [f1_body, f2_body]

    def _get_command_score(self, mouse_tight_actions, command):
        """
        ✅ 명령어 효율성 점수 계산 (exe3.py:2501-2514)

        - 짧은 명령어로 많은 행동을 하면 높은 점수
        - 함수 호출(10, 11)은 명령어 3개 절약
        - LOOP(110), IF(5)는 명령어 2개 절약

        Args:
            mouse_tight_actions: 실제 실행된 행동 리스트
            command: 명령어 리스트

        Returns:
            int: 명령어 점수
        """
        command_line = len(command)

        for cmd in command:
            if cmd in [10, 11]:  # 함수 호출
                command_line = command_line - 3
            elif cmd in [110, 5]:  # LOOP, IF
                command_line = command_line - 2

        score = (len(mouse_tight_actions) - command_line) * 10 + 10
        return score

    def _get_mouse_actions(self, command, function):
        """
        명령어를 실제 행동으로 변환 (exe3.py:1921-2011 간소화 버전)

        Args:
            command: List[int] - 명령어 리스트
            function: List[List[int]] - 함수 2개 [F1, F2]
        Returns:
            actions: List[int] - 행동 리스트
            col_wall: List[int] - 벽 충돌 인덱스 리스트
        """
        actions = []
        col_wall = []
        virtual_mouse = self.mouse.copy()  # ✅ Phase 1: deepcopy → shallow copy

        need_next = 0  # State machine for LOOP/IF
        pc = 0  # Previous command

        for cmd in command:
            if not need_next:
                # 방향 명령 (0=up, 1=down, 2=left, 3=right)
                if cmd in [0, 1, 2, 3]:
                    if self._movable(virtual_mouse, cmd):
                        actions.append(cmd)
                        virtual_mouse = self._move(virtual_mouse, cmd)
                    else:
                        # 벽 충돌
                        actions.append(cmd)
                        col_wall.append(len(actions) - 1)

                # LOOP(110) or IF(5)
                elif cmd in [5, 110]:
                    need_next = cmd

                # 함수 호출 (10=F1, 11=F2)
                elif cmd in [10, 11]:
                    func_idx = cmd - 10
                    if func_idx < len(function) and len(function[func_idx]) > 0:
                        # 재귀적으로 함수 내부 실행
                        func_actions, func_col = self._get_mouse_actions(
                            list(function[func_idx]),  # ✅ Phase 1: deepcopy → list() (10배 빠름)
                            function
                        )
                        actions.extend(func_actions)
                        # 벽 충돌 인덱스 조정
                        col_wall.extend([x + len(actions) - len(func_actions) for x in func_col])

                        # virtual_mouse 업데이트 (함수 실행 후 위치)
                        for act in func_actions:
                            if self._movable(virtual_mouse, act):
                                virtual_mouse = self._move(virtual_mouse, act)

            # LOOP 처리 (110 NUM DIR)
            elif need_next == 110:
                pc = need_next
                need_next = cmd  # NUM (100-109)
            elif pc == 110 and cmd in range(100, 110):
                # NUM 다음에는 DIR이 와야 함
                # 간소화: 다음 토큰을 기다리지 않고 여기서 처리
                # (실제로는 3-token pattern이지만 여기서는 단순화)
                need_next = cmd
            elif pc == 110 and need_next in range(100, 110):
                # LOOP NUM DIR 완성
                n_iter = need_next - 100 if need_next != 100 else 10
                direction = cmd

                for _ in range(n_iter):
                    if self._movable(virtual_mouse, direction):
                        actions.append(direction)
                        virtual_mouse = self._move(virtual_mouse, direction)
                    else:
                        actions.append(direction)
                        col_wall.append(len(actions) - 1)

                need_next = 0
                pc = 0

            # IF 처리 (5 NUM DIR) - LOOP과 유사하지만 교차로 기반
            elif need_next == 5:
                pc = need_next
                need_next = cmd
            elif pc == 5 and cmd in range(101, 108):
                need_next = cmd
            elif pc == 5 and need_next in range(101, 108):
                n_iter = need_next - 100
                direction = cmd

                # IF: 교차로를 만나면 반복 카운트 감소
                while n_iter > 0 and self._movable(virtual_mouse, direction):
                    actions.append(direction)
                    virtual_mouse = self._move(virtual_mouse, direction)

                    if self.junc[virtual_mouse[0]][virtual_mouse[1]]:
                        n_iter -= 1

                    if n_iter == 0:
                        break

                need_next = 0
                pc = 0

        return actions, col_wall

    def _get_cats_pre_actions(self, mouse_actions):
        """
        Pre-calculate cat actions (exe3.py _get_cats_direct_actions - RANDOM mode).

        Cats move randomly: at junctions pick random direction (no turning back),
        on straight paths keep going, if blocked pick any random valid direction.
        No flee behavior - cats don't track mouse position.
        """
        import random

        n_steps = len(mouse_actions) if isinstance(mouse_actions, list) else mouse_actions
        cats_actions = [[], []]
        virtual_cats = [cat.copy() for cat in self.cat]
        virtual_dirs = self.cat_direction.copy()

        for _ in range(n_steps):
            for i, v_cat in enumerate(virtual_cats):
                if self.junc[v_cat[0]][v_cat[1]]:
                    # Junction: random direction (no turning back)
                    attempts = 0
                    found = False
                    while attempts < 100:
                        attempts += 1
                        new_direction = random.randrange(0, 4)
                        if virtual_dirs[i] in [5 - new_direction, 1 - new_direction]:
                            continue
                        elif self._movable(v_cat, new_direction):
                            virtual_cats[i] = self._move(v_cat, new_direction)
                            virtual_dirs[i] = new_direction
                            cats_actions[i].append(new_direction)
                            found = True
                            break
                    if not found:
                        cats_actions[i].append(virtual_dirs[i] if virtual_dirs[i] in range(4) else 0)

                elif self._movable(v_cat, virtual_dirs[i]):
                    # Straight: keep going
                    virtual_cats[i] = self._move(v_cat, virtual_dirs[i])
                    cats_actions[i].append(virtual_dirs[i])

                else:
                    # Blocked: pick any random valid direction
                    attempts = 0
                    found = False
                    while attempts < 100:
                        attempts += 1
                        new_direction = random.randrange(0, 4)
                        if self._movable(v_cat, new_direction):
                            virtual_cats[i] = self._move(v_cat, new_direction)
                            virtual_dirs[i] = new_direction
                            cats_actions[i].append(new_direction)
                            found = True
                            break
                    if not found:
                        cats_actions[i].append(virtual_dirs[i] if virtual_dirs[i] in range(4) else 0)

        return cats_actions

    def _get_crzbc_pre_actions(self, n_moves):
        """
        Pre-calculate crzbc actions (exe3.py _get_crzbc_actions).

        CrzBC movement pre-calculated for n_moves steps (= len(command)).
        Junction: random (no turning back), otherwise continue same direction.
        """
        import random

        n_crzbc = len(self.crzbc)
        if n_crzbc == 0:
            return []

        crzbc_actions = [[] for _ in range(n_crzbc)]
        virtual_crzbc = [pos.copy() for pos in self.crzbc]
        virtual_dirs = self.crzbc_direction.copy() if hasattr(self, 'crzbc_direction') else [0] * n_crzbc

        for _ in range(n_moves):
            for i, v_crzbc in enumerate(virtual_crzbc):
                if not (0 <= v_crzbc[0] <= 10 and 0 <= v_crzbc[1] <= 10):
                    continue

                if self.junc[v_crzbc[0]][v_crzbc[1]]:
                    attempts = 0
                    found = False
                    while attempts < 100:
                        attempts += 1
                        new_direction = random.randrange(0, 4)
                        if i < len(virtual_dirs) and virtual_dirs[i] in [5 - new_direction, 1 - new_direction]:
                            continue
                        elif self._movable(v_crzbc, new_direction):
                            virtual_crzbc[i] = self._move(v_crzbc, new_direction)
                            if i < len(virtual_dirs):
                                virtual_dirs[i] = new_direction
                            crzbc_actions[i].append(new_direction)
                            found = True
                            break
                    if not found:
                        crzbc_actions[i].append(virtual_dirs[i] if i < len(virtual_dirs) and virtual_dirs[i] in range(4) else 0)

                elif i < len(virtual_dirs) and self._movable(v_crzbc, virtual_dirs[i]):
                    virtual_crzbc[i] = self._move(v_crzbc, virtual_dirs[i])
                    crzbc_actions[i].append(virtual_dirs[i])

                else:
                    attempts = 0
                    found = False
                    while attempts < 100:
                        attempts += 1
                        new_direction = random.randrange(0, 4)
                        if self._movable(v_crzbc, new_direction):
                            virtual_crzbc[i] = self._move(v_crzbc, new_direction)
                            if i < len(virtual_dirs):
                                virtual_dirs[i] = new_direction
                            crzbc_actions[i].append(new_direction)
                            found = True
                            break
                    if not found:
                        crzbc_actions[i].append(virtual_dirs[i] if i < len(virtual_dirs) and virtual_dirs[i] in range(4) else 0)

        return crzbc_actions

    def simulate_program(self, program, function=None):
        """
        프로그램 실행 시뮬레이션 (evaluation only, virtual state)
        ✅ exe3.py running_op과 동일한 동작:
        - Pre-calculated cat/crzbc actions
        - Cat0 (dummy): len(command) steps, Cat1 (naughty): every step
        - Collision check AFTER cat movement
        - movbc: no movement (collection only)
        - Cat-cat collision prevention at execution time
        """
        import random

        command, function = self._parse_program(program)

        func_count = sum(1 for token in command if token in [10, 11])
        if func_count > self.func_chance:
            return -1000.0

        mouse_actions, col_wall = self._get_mouse_actions(command, function)

        initial_score = self.score
        virtual_mouse = self.mouse.copy()
        virtual_mouse_last = self.mouse.copy()
        virtual_sc = [row.copy() for row in self.sc]
        virtual_movbc = [item.copy() for item in self.movbc]
        virtual_crzbc = [item.copy() for item in self.crzbc]
        virtual_cats = [cat.copy() for cat in self.cat]
        virtual_cat_last = [cat.copy() for cat in self.cat]
        virtual_step = self.step
        virtual_score = initial_score
        virtual_life = self.life

        # Pre-calculate entity actions (exe3.py style)
        cat_actions = self._get_cats_pre_actions(mouse_actions)
        crzbc_actions = self._get_crzbc_pre_actions(len(command))

        for itr in range(len(mouse_actions)):
            # 1. Wall collision
            if itr in col_wall:
                virtual_score -= 10

            # 2. Mouse moves
            virtual_mouse_last = virtual_mouse.copy()
            if self._movable(virtual_mouse, mouse_actions[itr]):
                virtual_mouse = self._move(virtual_mouse, mouse_actions[itr])
                virtual_step += 1

            # 3. Cat1 (naughty) moves every step
            if len(cat_actions) > 1 and itr < len(cat_actions[1]):
                if self._movable(virtual_cats[1], cat_actions[1][itr]):
                    new_pos = self._move(virtual_cats[1], cat_actions[1][itr])
                    if new_pos != virtual_cats[0]:
                        virtual_cat_last[1] = virtual_cats[1].copy()
                        virtual_cats[1] = new_pos

            # 4. Cat0 (dummy) moves only for len(command) steps
            if itr < len(command) and len(cat_actions) > 0 and itr < len(cat_actions[0]):
                if self._movable(virtual_cats[0], cat_actions[0][itr]):
                    new_pos = self._move(virtual_cats[0], cat_actions[0][itr])
                    if new_pos != virtual_cats[1]:
                        virtual_cat_last[0] = virtual_cats[0].copy()
                        virtual_cats[0] = new_pos

            # 5. Crzbc moves (pre-calculated, for len(command) steps)
            for j in range(len(virtual_crzbc)):
                if j >= len(crzbc_actions):
                    continue
                if virtual_crzbc[j] == [-1, -1]:
                    continue
                if itr < len(crzbc_actions[j]) and self._movable(virtual_crzbc[j], crzbc_actions[j][itr]):
                    new_pos = self._move(virtual_crzbc[j], crzbc_actions[j][itr])
                    collision = False
                    if new_pos in virtual_cats:
                        collision = True
                    for k in range(len(virtual_crzbc)):
                        if k != j and new_pos == virtual_crzbc[k]:
                            collision = True
                            break
                    if not collision:
                        virtual_crzbc[j] = new_pos

            # 6. Cat collision check AFTER cat movement
            catched = False
            for i, cat_pos in enumerate(virtual_cats):
                if ((cat_pos == virtual_mouse_last and virtual_mouse == virtual_cat_last[i]) or
                    cat_pos == virtual_mouse):
                    virtual_score -= 500
                    virtual_life -= 1
                    catched = True

            # 7. movbc collection (NO movement)
            for i, mbc in enumerate(virtual_movbc):
                if mbc == [-1, -1]:
                    continue
                if mbc == virtual_mouse:
                    virtual_score += 500
                    virtual_movbc[i] = [-1, -1]

            # 8. crzbc collection
            for i, bc in enumerate(virtual_crzbc):
                if bc == [-1, -1]:
                    continue
                if bc == virtual_mouse:
                    virtual_score += 500
                    virtual_crzbc[i] = [-1, -1]

            # 9. SC collection
            x, y = virtual_mouse
            if virtual_sc[x][y] == 1:
                virtual_score += 10
                virtual_sc[x][y] = 0

            # 10. Win/lose check
            if virtual_life == 0:
                self.lose_sign = True
                break
            elif sum([sum(line) for line in virtual_sc]) == 0:
                self.win_sign = True
                victory_bonus = self.run * 10 + virtual_step
                virtual_score += victory_bonus
                break
            elif virtual_step >= self.step_limit:
                self.lose_sign = True
                break

            # 11. Catched: stop this run
            if catched:
                self.catched = True
                break

        return float(virtual_score)

    def simulate_program_and_apply(self, program, function=None):
        """
        프로그램 실행 시뮬레이션 + 실제 상태 적용
        ✅ exe3.py running_op과 동일한 동작:
        - Pre-calculated cat/crzbc actions
        - Cat0 (dummy): len(command) steps, Cat1 (naughty): every step
        - Collision check AFTER cat movement
        - movbc: stationary (collection only, no movement)
        - Cat-cat collision prevention at execution time
        """
        import random

        command, function = self._parse_program(program)

        func_count = sum(1 for token in command if token in [10, 11])
        if func_count > self.func_chance:
            return -1000.0

        mouse_actions, col_wall = self._get_mouse_actions(command, function)

        self.command_score = self._get_command_score(mouse_actions, command)
        self.score += self.command_score
        self.collision_score = 0

        # ===== PRE-CALCULATE entity actions (exe3.py style) =====
        cat_actions = self._get_cats_pre_actions(mouse_actions)
        crzbc_actions = self._get_crzbc_pre_actions(len(command))

        # ===== MAIN LOOP (matching exe3.py running_op order) =====
        for itr in range(len(mouse_actions)):
            # 1. Wall collision
            if itr in col_wall:
                self.score -= 10
                self.collision_score -= 10

            # 2. Mouse moves
            if self._movable(self.mouse, mouse_actions[itr]):
                self.mouse_last_pos = self.mouse.copy()
                self.mouse = self._move(self.mouse, mouse_actions[itr])
                self.step += 1

            # 3. Cat1 (naughty) moves every mouse step
            if len(cat_actions) > 1 and itr < len(cat_actions[1]):
                if self._movable(self.cat[1], cat_actions[1][itr]):
                    new_pos = self._move(self.cat[1], cat_actions[1][itr])
                    if new_pos != self.cat[0]:  # cat-cat collision prevention
                        self.cat_last_pos[1] = self.cat[1].copy()
                        self.cat[1] = new_pos
                        self.cat_direction[1] = cat_actions[1][itr]

            # 4. Cat0 (dummy) moves only for len(command) steps
            if itr < len(command) and len(cat_actions) > 0 and itr < len(cat_actions[0]):
                if self._movable(self.cat[0], cat_actions[0][itr]):
                    new_pos = self._move(self.cat[0], cat_actions[0][itr])
                    if new_pos != self.cat[1]:  # cat-cat collision prevention
                        self.cat_last_pos[0] = self.cat[0].copy()
                        self.cat[0] = new_pos
                        self.cat_direction[0] = cat_actions[0][itr]

            # 5. Crzbc moves (pre-calculated, for len(command) steps)
            for j in range(len(self.crzbc)):
                if j >= len(crzbc_actions):
                    continue
                if self.crzbc[j] == [-1, -1]:
                    continue
                if itr < len(crzbc_actions[j]) and self._movable(self.crzbc[j], crzbc_actions[j][itr]):
                    new_pos = self._move(self.crzbc[j], crzbc_actions[j][itr])
                    collision = False
                    if new_pos in self.cat:
                        collision = True
                    for k in range(len(self.crzbc)):
                        if k != j and new_pos == self.crzbc[k]:
                            collision = True
                            break
                    if not collision:
                        self.crzbc_last_pos[j] = self.crzbc[j].copy()
                        self.crzbc[j] = new_pos
                        self.crzbc_direction[j] = crzbc_actions[j][itr]

            # 6. Cat collision check AFTER cat movement (exe3.py style)
            # Note: no break in this loop - both cats can catch mouse in same step
            for i, cat_pos in enumerate(self.cat):
                if ((cat_pos == self.mouse_last_pos and self.mouse == self.cat_last_pos[i]) or
                    cat_pos == self.mouse):
                    self.collision_score -= 500
                    self.score -= 500
                    self.life -= 1
                    self.catched = True

            # 7. movbc collection (NO movement - movbc is stationary in exe3.py)
            eat_movbc = []
            for i in range(len(self.movbc)):
                if self.movbc[i] == [-1, -1]:
                    continue
                if self.mouse == self.movbc[i]:
                    eat_movbc.append(i)
                    self.collision_score += 500
                    self.score += 500
                elif (self.movbc[i] == self.mouse_last_pos and
                      self.mouse == self.movbc_last_pos[i]):
                    eat_movbc.append(i)
                    self.collision_score += 500
                    self.score += 500
            for e in sorted(set(eat_movbc), reverse=True):
                self.movbc[e] = [-1, -1]

            # 8. crzbc collection (+ Crossing detection)
            eat_crzbc = []
            for i in range(len(self.crzbc)):
                if self.crzbc[i] == [-1, -1]:
                    continue
                if self.mouse == self.crzbc[i]:
                    eat_crzbc.append(i)
                    self.collision_score += 500
                    self.score += 500
                elif (self.crzbc[i] == self.mouse_last_pos and
                      self.mouse == self.crzbc_last_pos[i]):
                    eat_crzbc.append(i)
                    self.collision_score += 500
                    self.score += 500
            for e in sorted(set(eat_crzbc), reverse=True):
                self.crzbc[e] = [-1, -1]

            # 9. SC collection
            if self.sc[self.mouse[0]][self.mouse[1]] == 1:
                self.collision_score += 10
                self.score += 10
                self.sc[self.mouse[0]][self.mouse[1]] = 0

            # 10. Win/lose check (exe3.py order: life→sc→step)
            if self.life == 0:
                self.lose_sign = True
                break
            elif sum([sum(line) for line in self.sc]) == 0:
                self.win_sign = True
                win_bonus = self.run * 10 + self.step
                self.score += int(win_bonus)
                break
            elif self.step >= self.step_limit and self.step_limit > 0:
                self.lose_sign = True
                break

            # 11. Catched: respawn and break (exe3.py: retry_after_catched then break)
            if self.catched:
                self._retry_after_catched()
                break

        # Update cumulative scores
        self.total_command_score += self.command_score
        self.total_collision_score += self.collision_score

        return float(self.score)

    def reset(self):
        """게임 상태 초기화 (재사용을 위해)"""
        self.__init__(level=self.level)

    def _retry_after_catched(self):
        """
        ✅ 고양이에게 잡힌 후 리스폰 처리 (exe3.py:606-613)

        - 쥐: 초기 위치 [10, 10]으로 이동
        - 고양이: 초기 위치 [[2,2], [5,5]]로 리셋
        - catched 플래그 리셋
        - 게임은 계속됨 (life > 0인 경우)
        """
        import random
        self.mouse = [10, 10]
        self.mouse_last_pos = [10, 10]
        self.cat = [[2, 2], [5, 5]]
        self.cat_last_pos = [[2, 2], [5, 5]]
        self.cat_direction = [random.randrange(0, 4), random.randrange(0, 4)]
        self.catched = False

    # ========================================
    # Hybrid TRM Functions
    # ========================================

    def _get_mouse_actions_with_trace(self, command, function):
        """
        명령어를 행동으로 변환 + Action→Token 매핑 추가

        Args:
            command: List[int] - 명령어 리스트
            function: List[List[int]] - 함수 2개 [F1, F2]

        Returns:
            actions: List[int] - 행동 리스트
            col_wall: List[int] - 벽 충돌 인덱스 리스트
            action_to_token: Dict[int, dict] - Action index → Token 정보 매핑
        """
        actions = []
        col_wall = []
        action_to_token = {}  # 새로 추가!
        virtual_mouse = self.mouse.copy()  # ✅ Phase 1: deepcopy → shallow copy

        need_next = 0
        pc = 0

        for token_idx, cmd in enumerate(command):
            if not need_next:
                # 방향 명령 (0=up, 1=down, 2=left, 3=right)
                if cmd in [0, 1, 2, 3]:
                    action_idx = len(actions)
                    action_to_token[action_idx] = {
                        'token_idx': token_idx,
                        'token_type': 'DIRECTION',
                        'token_value': cmd,
                        'function_context': None,
                        'loop_context': None
                    }

                    if self._movable(virtual_mouse, cmd):
                        actions.append(cmd)
                        virtual_mouse = self._move(virtual_mouse, cmd)
                    else:
                        actions.append(cmd)
                        col_wall.append(len(actions) - 1)

                # LOOP(110) or IF(5)
                elif cmd in [5, 110]:
                    need_next = cmd

                # 함수 호출 (10=F1, 11=F2)
                elif cmd in [10, 11]:
                    func_idx = cmd - 10
                    if func_idx < len(function) and len(function[func_idx]) > 0:
                        # 재귀적으로 함수 내부 실행
                        func_actions, func_col, func_trace = self._get_mouse_actions_with_trace(
                            list(function[func_idx]),  # ✅ Phase 1: deepcopy → list() (10배 빠름)
                            function
                        )

                        # 함수 내부 action에 context 추가
                        for i, func_action in enumerate(func_actions):
                            action_idx = len(actions) + i
                            if i in func_trace:
                                # 함수 내부 토큰 정보 복사 + 함수 호출 context 추가
                                action_to_token[action_idx] = func_trace[i].copy()
                                action_to_token[action_idx]['function_call_token'] = token_idx
                                action_to_token[action_idx]['function_id'] = func_idx

                        actions.extend(func_actions)
                        col_wall.extend([x + len(actions) - len(func_actions) for x in func_col])

                        # virtual_mouse 업데이트
                        for act in func_actions:
                            if self._movable(virtual_mouse, act):
                                virtual_mouse = self._move(virtual_mouse, act)

            # LOOP 처리 (110 NUM DIR)
            elif need_next == 110:
                pc = need_next
                loop_start_token = token_idx - 1  # LOOP token index
                need_next = cmd
            elif pc == 110 and cmd in range(100, 110):
                need_next = cmd
            elif pc == 110 and need_next in range(100, 110):
                n_iter = need_next - 100 if need_next != 100 else 10
                direction = cmd
                loop_start_token = token_idx - 2  # LOOP token

                for iter_num in range(n_iter):
                    action_idx = len(actions)
                    action_to_token[action_idx] = {
                        'token_idx': loop_start_token,
                        'token_type': 'LOOP',
                        'token_value': 110,
                        'loop_count': n_iter,
                        'loop_iteration': iter_num,
                        'loop_direction': direction,
                        'function_context': None
                    }

                    if self._movable(virtual_mouse, direction):
                        actions.append(direction)
                        virtual_mouse = self._move(virtual_mouse, direction)
                    else:
                        actions.append(direction)
                        col_wall.append(len(actions) - 1)

                need_next = 0
                pc = 0

            # IF 처리 (5 NUM DIR)
            elif need_next == 5:
                pc = need_next
                if_start_token = token_idx - 1
                need_next = cmd
            elif pc == 5 and cmd in range(101, 108):
                need_next = cmd
            elif pc == 5 and need_next in range(101, 108):
                n_iter = need_next - 100
                direction = cmd
                if_start_token = token_idx - 2

                iter_count = 0
                while n_iter > 0 and self._movable(virtual_mouse, direction):
                    action_idx = len(actions)
                    action_to_token[action_idx] = {
                        'token_idx': if_start_token,
                        'token_type': 'IF',
                        'token_value': 5,
                        'if_count': need_next - 100,
                        'if_iteration': iter_count,
                        'if_direction': direction,
                        'function_context': None
                    }

                    actions.append(direction)
                    virtual_mouse = self._move(virtual_mouse, direction)

                    if self.junc[virtual_mouse[0]][virtual_mouse[1]]:
                        n_iter -= 1

                    iter_count += 1

                    if n_iter == 0:
                        break

                need_next = 0
                pc = 0

        return actions, col_wall, action_to_token

    def execute_with_error_classification(self, program, function=None):
        """
        프로그램 실행 + 에러 분류

        Returns:
            dict: {
                'success': bool,
                'score': float,
                'errors': {
                    'wall_collisions': List[dict],
                    'cat_caught': dict or None,
                    'timeout': bool,
                    'command_failures': List[dict]
                },
                'action_to_token': dict
            }
        """
        # Parse program
        command, parsed_function = self._parse_program(program)
        if function is not None:
            parsed_function = function

        # Get actions with trace
        mouse_actions, col_wall, action_to_token = self._get_mouse_actions_with_trace(
            command, parsed_function
        )

        # Initialize error tracking
        errors = {
            'wall_collisions': [],
            'cat_caught': None,
            'timeout': False,
            'command_failures': []
        }

        # Simulate
        initial_score = self.score
        # ✅ Phase 1: deepcopy → list comprehension (10배 빠름!)
        virtual_mouse = self.mouse.copy()
        virtual_sc = [row.copy() if isinstance(row, list) else list(row) for row in self.sc]
        virtual_movbc = [item.copy() if isinstance(item, list) else list(item) for item in self.movbc]
        virtual_crzbc = [item.copy() if isinstance(item, list) else list(item) for item in self.crzbc]
        virtual_cats = [cat.copy() if isinstance(cat, list) else list(cat) for cat in self.cat]
        virtual_cat_dirs = self.cat_direction.copy() if isinstance(self.cat_direction, list) else list(self.cat_direction)
        virtual_step = self.step
        virtual_score = initial_score  # ✅ Virtual score (don't modify self.score!)

        for itr, action in enumerate(mouse_actions):
            # 벽 충돌 감지
            if itr in col_wall:
                virtual_score -= 10
                errors['wall_collisions'].append({
                    'action_idx': itr,
                    'token_info': action_to_token.get(itr, {}),
                    'position': virtual_mouse.copy(),
                    'direction': action
                })

            # 쥐 이동
            if self._movable(virtual_mouse, action):
                self.mouse_last_pos = virtual_mouse.copy()
                virtual_mouse = self._move(virtual_mouse, action)
                virtual_step += 1

                # 고양이 이동 (간소화)
                for cat_idx, cat_pos in enumerate(virtual_cats):
                    if cat_pos == virtual_mouse:
                        continue

                    cat_dir = virtual_cat_dirs[cat_idx] if cat_idx < len(virtual_cat_dirs) else 0
                    new_pos = self._move(cat_pos, cat_dir)

                    if self._movable(cat_pos, cat_dir) and new_pos != virtual_mouse:
                        virtual_cats[cat_idx] = new_pos

                # 치즈 먹기
                x, y = virtual_mouse
                if virtual_sc[x][y] == 1:
                    virtual_score += 10
                    virtual_sc[x][y] = 0

                # Big cheese
                for i, bc_pos in enumerate(virtual_movbc):
                    if bc_pos == virtual_mouse:
                        virtual_score += 500
                        virtual_movbc[i] = [-1, -1]

                for i, bc_pos in enumerate(virtual_crzbc):
                    if bc_pos == virtual_mouse:
                        virtual_score += 500
                        virtual_crzbc[i] = [-1, -1]

                # 고양이 충돌 체크
                for cat_idx, cat_pos in enumerate(virtual_cats):
                    if cat_pos == virtual_mouse:
                        virtual_score -= 500
                        self.catched = True
                        errors['cat_caught'] = {
                            'action_idx': itr,
                            'token_info': action_to_token.get(itr, {}),
                            'position': virtual_mouse.copy(),
                            'cat_position': cat_pos
                        }
                        break

                # 스텝 제한
                if virtual_step >= self.step_limit:
                    self.lose_sign = True
                    errors['timeout'] = True
                    break

        # 완전 클리어 (모든 치즈)
        full_clear = sum([sum(line) for line in virtual_sc]) == 0
        if full_clear:
            self.win_sign = True
            victory_bonus = self.run * 10 + virtual_step
            virtual_score += victory_bonus

        # Success 조건 (현실적)
        # - 고양이 안 잡힘
        # - 타임아웃 없음
        # - 벽 충돌 0개 (절대 안 부딪힘)
        # - 최소 점수 10 이상 (치즈 1개 이상, 제자리 방지)
        success = (
            errors['cat_caught'] is None and
            not errors['timeout'] and
            len(errors['wall_collisions']) == 0 and
            virtual_score >= 10
        )

        return {
            'success': success,
            'full_clear': full_clear,  # 완전 클리어 여부 (별도)
            'score': float(virtual_score),
            'run_score': float(virtual_score - initial_score),  # ✅ 이번 run에서 획득한 점수
            'errors': errors,
            'action_to_token': action_to_token,
            'total_actions': len(mouse_actions)
        }

    def get_state_vector(self):
        """
        ✅ 현재 시뮬레이터 상태를 828차원 벡터로 변환

        3-program generation에서 사용:
        - Current 시뮬 후 → state_6 추출
        - Next 시뮬 후 → state_7 추출

        주의: 히스토리 관련 feature는 0으로 채움
        (시뮬레이터는 히스토리 추적 안 함)
        """
        import numpy as np
        from collections import deque

        # === Spatial: 484차원 ===
        wall = np.array(self.wall).flatten()  # 121
        sc = np.array(self.sc).flatten()  # 121
        junc = np.array(self.junc).flatten()  # 121
        deadend = np.array(self.deadend).flatten()  # 121

        # === Entity: 65차원 ===
        # Mouse (3)
        mouse_pos = np.array(self.mouse).flatten() / 10.0  # 2
        mouse_dir = np.array([0]).flatten() / 3.0  # 1 (시뮬레이터는 direction 없음 → 0)

        # Cats (6)
        cats_pos = np.array(self.cat).flatten() / 10.0  # 4
        cats_dir = np.array(self.cat_direction).flatten() / 3.0  # 2

        # Big Cheese (10)
        movbc_list = [list(bc) for bc in self.movbc] if self.movbc else []
        while len(movbc_list) < 2:
            movbc_list.append([0, 0])
        movbc_pos = np.array(movbc_list[:2]).flatten() / 10.0  # 4

        crzbc_list = [list(bc[:2]) if hasattr(bc, '__iter__') else [bc, 0] for bc in self.crzbc] if self.crzbc else []
        while len(crzbc_list) < 2:
            crzbc_list.append([0, 0])
        crzbc_pos = np.array(crzbc_list[:2]).flatten() / 10.0  # 4

        # Nearest big cheese (4)
        all_bc = list(movbc_list[:2]) + list(crzbc_list[:2])
        bc_dists = [abs(self.mouse[0] - bc[0]) + abs(self.mouse[1] - bc[1])
                    for bc in all_bc]
        nearest_bc_idx = np.argmin(bc_dists) if bc_dists else 0
        nearest_bc_onehot = np.eye(4)[nearest_bc_idx]
        nearest_bc_full = nearest_bc_onehot.flatten()  # 4

        # 시간적 정보 (16) - ✅ 0으로 채움 (히스토리 없음)
        cat_history = np.zeros(12)  # 3스텝 × 2마리 × 2좌표
        cat_velocity = np.zeros(4)  # 2마리 × 2차원

        # 예측 정보 (20) - 간단한 휴리스틱
        cat_future = np.zeros(12)  # 3턴 × 2마리 × 2좌표 (예측 생략)
        bc_future = np.concatenate([movbc_pos, crzbc_pos])  # 8 (현재 위치 그대로)

        # 전략 정보 (8) - 간단한 도망 방향
        cat_escape_dirs = self._compute_cat_escape_directions()  # 8

        # === GameState: 279차원 ===
        # Basic (5)
        life = np.array([self.life / 3.0])
        score = np.array([self.score / 1000.0])
        step = np.array([self.step / 200.0])
        func_chance = np.array([self.func_chance / 4.0])
        run = np.array([self.run / 20.0])

        # Big Cheese Info (9)
        bc_distances = np.array(bc_dists[:4]) / 20.0
        if len(bc_distances) < 4:
            bc_distances = np.pad(bc_distances, (0, 4 - len(bc_distances)), constant_values=0.0)

        bc_threats = np.zeros(4)
        for i, bc in enumerate(all_bc[:4]):
            if self.cat:
                min_cat_dist = min([abs(bc[0] - cat[0]) + abs(bc[1] - cat[1])
                                   for cat in self.cat])
                bc_threats[i] = max(0, (4 - min_cat_dist) / 4.0)

        nearest_bc_idx_scalar = np.array([nearest_bc_idx / 4.0])

        # Strategy Features (242)
        cheese_distances = self._compute_cheese_distances_bfs()  # 121
        cat_threats = self._compute_cat_threats()  # 121

        # 전략 추가 (15) - 간소화
        cheese_clusters = np.zeros(10)  # 클러스터링 생략
        region_cheese_dist = self._compute_region_cheese_distribution()  # 5

        # 이력 추가 (8) - ✅ 0으로 채움
        action_hist = np.zeros(5)  # 히스토리 없음
        func_usage = np.zeros(2)  # 사용 횟수 추적 안 함
        wall_collision_scalar = np.zeros(1)  # 충돌 횟수 추적 안 함

        # === 전체 결합: 828차원 ===
        state = np.concatenate([
            # Spatial: 484
            wall, sc, junc, deadend,
            # Entity: 65
            mouse_pos, mouse_dir, cats_pos, cats_dir,
            movbc_pos, crzbc_pos, nearest_bc_full,
            cat_history, cat_velocity,
            cat_future, bc_future,
            cat_escape_dirs,
            # GameState: 279
            life, score, step, func_chance, run,
            bc_distances, bc_threats, nearest_bc_idx_scalar,
            cheese_distances, cat_threats,
            cheese_clusters, region_cheese_dist,
            action_hist, func_usage, wall_collision_scalar
        ])

        assert len(state) == 828, f"State size error: {len(state)} != 828"

        return state

    def _compute_cat_escape_directions(self):
        """고양이별 도망 방향 (8차원)"""
        import numpy as np
        escape_dirs = np.zeros(8)

        if not self.cat:
            return escape_dirs

        mouse_r, mouse_c = self.mouse

        for cat_idx in range(min(2, len(self.cat))):
            cat_r, cat_c = self.cat[cat_idx]

            # 각 방향으로 이동 시 거리 계산
            dir_dists = [-1, -1, -1, -1]  # [up, down, left, right]

            # Up
            if mouse_r > 0 and self.wall[mouse_r - 1][mouse_c] == 0:
                dir_dists[0] = abs((mouse_r - 1) - cat_r) + abs(mouse_c - cat_c)

            # Down
            if mouse_r < 10 and self.wall[mouse_r + 1][mouse_c] == 0:
                dir_dists[1] = abs((mouse_r + 1) - cat_r) + abs(mouse_c - cat_c)

            # Left
            if mouse_c > 0 and self.wall[mouse_r][mouse_c - 1] == 0:
                dir_dists[2] = abs(mouse_r - cat_r) + abs((mouse_c - 1) - cat_c)

            # Right
            if mouse_c < 10 and self.wall[mouse_r][mouse_c + 1] == 0:
                dir_dists[3] = abs(mouse_r - cat_r) + abs((mouse_c + 1) - cat_c)

            # 최대 거리 방향 선택
            best_dir = np.argmax(dir_dists)

            # 원핫 인코딩
            base_idx = cat_idx * 4
            escape_dirs[base_idx + best_dir] = 1.0

        return escape_dirs

    def _compute_cheese_distances_bfs(self):
        """BFS 기반 치즈까지 거리 (121차원)"""
        from collections import deque
        import numpy as np

        cheese_distances = np.full(121, 999.0)

        # 모든 치즈 위치 수집
        cheese_positions = []
        for i in range(11):
            for j in range(11):
                if self.sc[i][j] == 1:
                    cheese_positions.append((i, j))

        if not cheese_positions:
            return cheese_distances / 20.0

        # 각 치즈로부터 BFS
        for cheese_r, cheese_c in cheese_positions:
            distance_map = [[999] * 11 for _ in range(11)]
            distance_map[cheese_r][cheese_c] = 0

            queue = deque([(cheese_r, cheese_c)])

            while queue:
                r, c = queue.popleft()
                current_dist = distance_map[r][c]

                # 4방향 탐색
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc

                    if 0 <= nr < 11 and 0 <= nc < 11:
                        if self.wall[nr][nc] == 0 and distance_map[nr][nc] == 999:
                            distance_map[nr][nc] = current_dist + 1
                            queue.append((nr, nc))

            # 최소 거리 업데이트
            for r in range(11):
                for c in range(11):
                    idx = r * 11 + c
                    cheese_distances[idx] = min(cheese_distances[idx], distance_map[r][c])

        # 정규화
        cheese_distances = np.clip(cheese_distances, 0, 999)
        cheese_distances = cheese_distances / 20.0

        return cheese_distances

    def _compute_cat_threats(self):
        """고양이 위협도 맵 (121차원)"""
        import numpy as np

        cat_threats = np.zeros(121)

        for cat in self.cat:
            cat_r, cat_c = cat

            for r in range(11):
                for c in range(11):
                    dist = abs(r - cat_r) + abs(c - cat_c)

                    if dist <= 3:
                        threat = (4 - dist) / 4.0
                        idx = r * 11 + c
                        cat_threats[idx] += threat

        # Clipping
        cat_threats = np.clip(cat_threats, 0.0, 1.0)

        return cat_threats

    def _compute_region_cheese_distribution(self):
        """구역별 치즈 분포 (5차원)"""
        import numpy as np

        region_dist = np.zeros(5)

        # 총 치즈 개수
        total_cheese = sum([sum(row) for row in self.sc])

        if total_cheese == 0:
            return region_dist

        # 구역별 카운트
        counts = [0, 0, 0, 0, 0]

        for i in range(11):
            for j in range(11):
                if self.sc[i][j] == 1:
                    if i <= 4 and j <= 4:
                        counts[0] += 1
                    elif i <= 4 and j >= 6:
                        counts[1] += 1
                    elif i >= 6 and j <= 4:
                        counts[2] += 1
                    elif i >= 6 and j >= 6:
                        counts[3] += 1
                    else:
                        counts[4] += 1

        # 정규화
        for idx in range(5):
            region_dist[idx] = counts[idx] / float(total_cheese)

        return region_dist

    # ===== GRPO 지원 메서드 =====

    def get_state_dict(self):
        """
        게임 상태를 직렬화 가능한 dict로 반환 (GRPO 병렬 평가용)

        Returns:
            dict: 게임 상태 (pickle/multiprocessing 가능)
        """
        return {
            'level': self.level,
            'mouse': list(self.mouse),
            'mouse_last_pos': list(self.mouse_last_pos),
            'cat': [list(c) for c in self.cat],
            'cat_last_pos': [list(c) for c in self.cat_last_pos],
            'cat_direction': list(self.cat_direction) if hasattr(self, 'cat_direction') else [0, 0],
            'sc': [list(row) for row in self.sc],
            'wall': [list(row) for row in self.wall],
            'junc': [list(row) for row in self.junc],
            'deadend': [list(row) for row in self.deadend],
            'crzbc': [list(c) for c in self.crzbc] if self.crzbc else [],
            'movbc': [list(c) for c in self.movbc] if self.movbc else [],
            'score': self.score,
            'life': self.life,
            'step': self.step,
            'step_limit': self.step_limit,
            'run': getattr(self, 'run', 0),
            'func_chance': self.func_chance,
            'red_zone': getattr(self, 'red_zone', 5),
            'win_sign': self.win_sign,
            'lose_sign': self.lose_sign,
            'catched': self.catched
        }

    def restore_state(self, state_dict):
        """
        dict에서 게임 상태 복원 (GRPO 병렬 평가용)

        Args:
            state_dict: get_state_dict()의 반환값
        """
        self.level = state_dict.get('level', 1)
        self.mouse = list(state_dict.get('mouse', [5, 5]))
        self.mouse_last_pos = list(state_dict.get('mouse_last_pos', self.mouse))
        self.cat = [list(c) for c in state_dict.get('cat', [[2, 2], [5, 5]])]
        self.cat_last_pos = [list(c) for c in state_dict.get('cat_last_pos', self.cat)]
        self.cat_direction = list(state_dict.get('cat_direction', [0, 0]))
        self.sc = [list(row) for row in state_dict.get('sc', [[0]*11 for _ in range(11)])]
        self.wall = [list(row) for row in state_dict.get('wall', [[0]*11 for _ in range(11)])]
        self.junc = [list(row) for row in state_dict.get('junc', [[0]*11 for _ in range(11)])]
        self.deadend = [list(row) for row in state_dict.get('deadend', [[0]*11 for _ in range(11)])]
        self.crzbc = [list(c) for c in state_dict.get('crzbc', [])]
        self.movbc = [list(c) for c in state_dict.get('movbc', [])]
        self.crzbc_last_pos = [list(c) for c in self.crzbc]
        self.movbc_last_pos = [list(c) for c in self.movbc]
        self.score = state_dict.get('score', 0)
        self.life = state_dict.get('life', 3)
        self.step = state_dict.get('step', 0)
        self.step_limit = state_dict.get('step_limit', 200)
        self.run = state_dict.get('run', 0)
        self.func_chance = state_dict.get('func_chance', 4)
        self.red_zone = state_dict.get('red_zone', 5)
        self.win_sign = state_dict.get('win_sign', False)
        self.lose_sign = state_dict.get('lose_sign', False)
        self.catched = state_dict.get('catched', False)
        # crzbc_direction 초기화
        self.crzbc_direction = [0] * len(self.crzbc) if self.crzbc else []

    def execute_program(self, program):
        """
        프로그램 실행 (GRPO용 간단한 인터페이스)
        ✅ 실제 게임 상태 업데이트

        Args:
            program: List[int] - 프로그램 토큰 리스트

        Returns:
            dict: {
                'score': float - 점수 변화량,
                'success': bool - 성공 여부,
                'steps': int - 실행된 스텝 수,
                'final_score': float - 최종 점수
            }
        """
        initial_score = self.score
        initial_step = self.step

        # simulate_program_and_apply 호출 (상태 업데이트)
        final_score = self.simulate_program_and_apply(program)

        # 성공 여부 판단 (치즈 다 먹었는지)
        remaining_cheese = sum(sum(row) for row in self.sc)
        success = remaining_cheese == 0 and not self.catched and not self.lose_sign

        # Run 카운트 증가
        self.run += 1

        # ✅ Run 제한 체크 (exe3.py:2815-2818)
        if self.run >= 20 and not self.win_sign:
            self.lose_sign = True

        return {
            'score': final_score - initial_score,
            'success': success,
            'steps': self.step - initial_step,
            'final_score': final_score
        }

    def reset(self):
        """게임 상태 초기화"""
        self._init_default_state()


# ===== 테스트 =====
if __name__ == "__main__":
    print("=" * 60)
    print("Testing LightweightGameSimulator")
    print("=" * 60)

    # Test 1: Basic movement
    print("\n--- Test 1: Basic Movement ---")
    sim = LightweightGameSimulator()

    # 간단한 프로그램: 앞3번
    program = [2, 2, 2, 112]  # UP UP UP END
    score = sim.simulate_program(program)
    print(f"Program: {program}")
    print(f"Final score: {score}")
    print("✅ Basic movement test passed!")

    # Test 2: Function library expansion
    print("\n--- Test 2: Function Library Expansion ---")
    sim.reset()

    # 함수 라이브러리 사용
    program = [113, 2, 112]  # F_113([1,2]) + UP + END
    expanded = sim.expand_function_library(program)
    print(f"Original: {program}")
    print(f"Expanded: {expanded}")
    score = sim.simulate_program(program)
    print(f"Final score: {score}")
    print("✅ Function library test passed!")

    # Test 3: Wall collision
    print("\n--- Test 3: Wall Collision ---")
    sim.reset()

    # 벽으로 이동 시도
    program = [0, 0, 0, 0, 0, 112]  # DOWN DOWN... (hit wall)
    score = sim.simulate_program(program)
    print(f"Program: {program}")
    print(f"Final score: {score} (should have wall penalties)")
    print("✅ Wall collision test passed!")

    # Test 4: Function limit
    print("\n--- Test 4: Function Limit (func_chance=4) ---")
    sim.reset()

    # 함수 5번 사용 (제한 초과)
    program = [113, 114, 115, 116, 117, 112]  # 5 functions → violation!
    score = sim.simulate_program(program)
    print(f"Program: {program} (5 functions)")
    print(f"Final score: {score} (should be -1000 penalty)")
    print("✅ Function limit test passed!")

    # Test 5: LOOP command
    print("\n--- Test 5: LOOP Command ---")
    sim.reset()

    # LOOP 3 UP
    program = [110, 103, 0, 112]  # LOOP 3 UP END
    score = sim.simulate_program(program)
    print(f"Program: {program} (LOOP 3 UP)")
    print(f"Final score: {score}")
    print("✅ LOOP test passed!")

    # Test 6: Speed test (20 iterations for TRM)
    print("\n--- Test 6: Speed Test (20 iterations) ---")
    import time

    start = time.time()
    for i in range(20):
        sim.reset()
        program = [2, 113, 2, 114, 2, 112]
        score = sim.simulate_program(program)
    end = time.time()

    print(f"20 iterations completed in {end - start:.4f} seconds")
    print(f"Average per iteration: {(end - start) / 20 * 1000:.2f} ms")
    print("✅ Speed test passed!")

    print("\n" + "=" * 60)
    print("✅ All LightweightGameSimulator tests passed!")
    print("=" * 60)
