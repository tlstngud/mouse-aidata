#pragma once

#include <cstdint>

namespace simulator {

// ============================================================
// 맵 크기
// ============================================================
constexpr int MAP_SIZE = 11;
constexpr int TOTAL_CELLS = MAP_SIZE * MAP_SIZE;  // 121

// ============================================================
// 방향 (절대 좌표 - Python과 동일)
// 0 = UP    (x -= 1, 위로)
// 1 = DOWN  (x += 1, 아래로)
// 2 = LEFT  (y -= 1, 왼쪽)
// 3 = RIGHT (y += 1, 오른쪽)
// ============================================================
namespace Direction {
    constexpr int UP = 0;
    constexpr int DOWN = 1;
    constexpr int LEFT = 2;
    constexpr int RIGHT = 3;
    constexpr int COUNT = 4;

    // 방향에 따른 이동 벡터 (dx, dy)
    constexpr int DX[4] = {-1, 1, 0, 0};
    constexpr int DY[4] = {0, 0, -1, 1};

    // 반대 방향
    constexpr int OPPOSITE[4] = {1, 0, 3, 2};  // UP<->DOWN, LEFT<->RIGHT
}

// ============================================================
// 토큰 타입 (Python lightweight_simulator.py와 동일)
// ============================================================
namespace Token {
    // 방향 토큰
    constexpr int DIR_UP = 0;
    constexpr int DIR_DOWN = 1;
    constexpr int DIR_LEFT = 2;
    constexpr int DIR_RIGHT = 3;

    // 제어 토큰
    constexpr int IF = 5;           // 조건 분기 (교차로)
    constexpr int FUNC_F1 = 10;     // 함수 1 호출
    constexpr int FUNC_F2 = 11;     // 함수 2 호출

    // 반복 횟수 (100-109)
    constexpr int NUM_BASE = 100;   // 100 = 10회, 101-109 = 1-9회
    constexpr int NUM_10 = 100;
    constexpr int NUM_1 = 101;
    constexpr int NUM_7 = 107;      // IF용 최대값 (Python: range(101, 108))
    constexpr int NUM_9 = 109;

    // 루프
    constexpr int LOOP = 110;

    // 종료
    constexpr int END = 112;

    // 함수 라이브러리 (113-998)
    constexpr int FUNC_LIB_START = 113;
    constexpr int FUNC_LIB_END = 998;

    // 빈칸 (무시)
    constexpr int EMPTY = 999;

    // 유틸리티 함수
    inline bool is_direction(int token) {
        return token >= 0 && token <= 3;
    }

    inline bool is_num(int token) {
        return token >= NUM_BASE && token <= NUM_9;
    }

    // IF 명령어용 숫자 체크 (Python: range(101, 108) = 1-7만 허용)
    inline bool is_if_num(int token) {
        return token >= NUM_1 && token <= NUM_7;
    }

    inline int get_num_value(int token) {
        if (token == NUM_10) return 10;
        return token - NUM_BASE;
    }

    inline bool is_func_lib(int token) {
        return token >= FUNC_LIB_START && token <= FUNC_LIB_END;
    }
}

// ============================================================
// 점수 (Python과 동일)
// ============================================================
namespace Score {
    constexpr int SMALL_CHEESE = 10;      // 작은 치즈 수집
    constexpr int BIG_CHEESE = 500;       // 큰 치즈 수집 (movbc, crzbc)
    constexpr int CAT_COLLISION = -500;   // 고양이 충돌
    constexpr int WALL_COLLISION = -10;   // 벽 충돌
}

// ============================================================
// 게임 설정
// ============================================================
namespace Config {
    constexpr int DEFAULT_LIFE = 3;
    constexpr int DEFAULT_STEP_LIMIT = 200;
    constexpr int DEFAULT_RED_ZONE = 5;
    constexpr int DEFAULT_FUNC_CHANCE = 4;
    constexpr int NUM_CATS = 2;
    constexpr int NUM_MOVBC = 2;
    constexpr int NUM_CRZBC = 2;
    constexpr int MAX_RANDOM_TRIES = 100;
}

} // namespace simulator
