"""
C++ 시뮬레이터 어댑터 (드롭인 대체)

C++ 확장 모듈이 있으면 사용하고, 없으면 Python 폴백
"""

try:
    import cpp_simulator as _cpp
    _USE_CPP = True
    print("[CPP] C++ Simulator loaded - 13x faster!")
except ImportError:
    _USE_CPP = False
    print("[PY] Using Python Simulator (fallback)")


if _USE_CPP:
    # 전역 캐시 레벨 추적 (레벨별 캐시 관리)
    _CACHE_INITIALIZED_LEVEL = None

    class LightweightGameSimulator:
        """C++ 기반 시뮬레이터 래퍼"""

        def __init__(self, level=1):
            global _CACHE_INITIALIZED_LEVEL

            self._sim = _cpp.Simulator(level)
            self.level = level
            self._run = 0
            self._catched = False

            # BFS 거리 맵 캐시 초기화 (레벨별 관리)
            # 다른 레벨로 요청하면 캐시 재초기화 필요
            if _CACHE_INITIALIZED_LEVEL is None or _CACHE_INITIALIZED_LEVEL != level:
                if _CACHE_INITIALIZED_LEVEL is not None and _CACHE_INITIALIZED_LEVEL != level:
                    print(f"[CPP] Warning: BFS cache was for level {_CACHE_INITIALIZED_LEVEL}, reinitializing for level {level}")
                self._sim.initialize_cache()
                _CACHE_INITIALIZED_LEVEL = level
                print(f"[CPP] BFS distance cache initialized for level {level} (121 positions)")

        def simulate_program(self, program):
            """프로그램 실행 후 점수 반환 (상태 변경 없음)"""
            return self._sim.simulate_program(program)

        def simulate_program_and_apply(self, program):
            """프로그램 실행 후 점수 반환 (C++ 사용, 상태 변경 없음)

            C++ simulate_program은 상태를 변경하지 않음
            상태 변경이 필요하면 execute_program 사용
            """
            return self._sim.simulate_program(program)

        def restore_state(self, state_dict):
            """Python dict에서 상태 복원"""
            self._sim.restore_state(state_dict)
            self._run = state_dict.get('run', 0)
            self._catched = state_dict.get('catched', False)

        def get_state_dict(self):
            """현재 상태를 Python dict로 반환"""
            state = self._sim.get_state_dict()
            state['run'] = self._run
            return state

        def reset(self):
            """초기 상태로 리셋"""
            self._sim.reset()
            self._run = 0
            self._catched = False

        def execute_program(self, program):
            """프로그램 실행 (GRPO용 인터페이스)

            Python 폴백: C++는 상태 수정 미지원
            """
            # Python 폴백 사용
            from lightweight_simulator import LightweightGameSimulator as PySimulator
            py_sim = PySimulator(level=self.level)
            py_sim.restore_state(self.get_state_dict())
            result = py_sim.execute_program(program)

            # 상태 동기화
            self.restore_state(py_sim.get_state_dict())
            return result

        @property
        def score(self):
            return self._sim.score

        @property
        def life(self):
            return self._sim.life

        @property
        def step(self):
            return self._sim.step

        @property
        def run(self):
            return self._run

        @run.setter
        def run(self, value):
            self._run = value

        @property
        def win_sign(self):
            return self._sim.win_sign

        @property
        def lose_sign(self):
            return self._sim.lose_sign

        @property
        def catched(self):
            return self._catched

        @property
        def sc(self):
            """작은 치즈 맵 (호환성용)"""
            return self._sim.get_state_dict()['sc']

        @property
        def movbc(self):
            """움직이는 빅치즈 좌표 (호환성용)"""
            return self._sim.get_state_dict()['movbc']

        @property
        def crzbc(self):
            """크레이지 빅치즈 좌표 (호환성용)"""
            return self._sim.get_state_dict()['crzbc']


    def batch_simulate(programs, initial_state, num_threads=0):
        """배치 시뮬레이션 (병렬 처리)

        Args:
            programs: 프로그램 리스트
            initial_state: 초기 상태 dict
            num_threads: 스레드 수 (0=자동)

        Returns:
            각 프로그램의 점수 리스트
        """
        return _cpp.batch_simulate(programs, initial_state, num_threads)


    # 상수 노출
    MAP_SIZE = _cpp.MAP_SIZE
    TOKEN_END = _cpp.TOKEN_END
    TOKEN_LOOP = _cpp.TOKEN_LOOP

else:
    # Python 폴백
    from lightweight_simulator import LightweightGameSimulator

    def batch_simulate(programs, initial_state, num_threads=0):
        """Python 순차 처리 폴백"""
        results = []
        sim = LightweightGameSimulator(level=3)
        for prog in programs:
            sim.restore_state(initial_state)
            results.append(sim.simulate_program(prog))
        return results

    MAP_SIZE = 11
    TOKEN_END = 112
    TOKEN_LOOP = 110


# 공통 유틸리티
def create_simulator(level=3):
    """시뮬레이터 생성 헬퍼"""
    return LightweightGameSimulator(level)


def is_cpp_available():
    """C++ 확장 사용 가능 여부"""
    return _USE_CPP
