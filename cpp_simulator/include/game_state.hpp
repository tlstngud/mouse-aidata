#pragma once

#include <array>
#include <cstdint>
#include <cstring>
#include "constants.hpp"

namespace simulator {

// ============================================================
// 11x11 그리드 맵 타입
// ============================================================
using GridMap = std::array<std::array<int8_t, MAP_SIZE>, MAP_SIZE>;

// ============================================================
// 2D 위치
// ============================================================
struct Position {
    int8_t x;
    int8_t y;

    Position() : x(0), y(0) {}
    Position(int8_t x_, int8_t y_) : x(x_), y(y_) {}

    bool operator==(const Position& other) const {
        return x == other.x && y == other.y;
    }

    bool operator!=(const Position& other) const {
        return !(*this == other);
    }

    bool is_valid() const {
        return x >= 0 && x < MAP_SIZE && y >= 0 && y < MAP_SIZE;
    }

    // 방향으로 이동
    Position move(int dir) const {
        return Position(
            static_cast<int8_t>(x + Direction::DX[dir]),
            static_cast<int8_t>(y + Direction::DY[dir])
        );
    }
};

// ============================================================
// 엔티티 (고양이, 빅치즈)
// ============================================================
struct Entity {
    Position pos;
    Position last_pos;
    int8_t direction;
    bool active;  // 빅치즈: false면 이미 먹힘

    Entity() : pos(), last_pos(), direction(0), active(true) {}
};

// ============================================================
// 게임 상태 (Python LightweightGameSimulator와 1:1 대응)
// ============================================================
struct GameState {
    // ========== 맵 데이터 (484 bytes) ==========
    GridMap wall;       // 벽 (0=통과, 1=벽)
    GridMap sc;         // 작은 치즈 (0=없음, 1=있음)
    GridMap junc;       // 교차로
    GridMap deadend;    // 막다른 길

    // ========== 엔티티 ==========
    Position mouse;
    Position mouse_last;
    std::array<Entity, Config::NUM_CATS> cats;      // 고양이 2마리
    std::array<Entity, Config::NUM_MOVBC> movbc;    // 이동 빅치즈 2개
    std::array<Entity, Config::NUM_CRZBC> crzbc;    // 미친 빅치즈 2개

    // ========== 게임 상태 ==========
    int32_t score;
    int16_t life;
    int16_t step;
    int16_t step_limit;
    int16_t run;
    int8_t func_chance;
    int8_t red_zone;

    // ========== 플래그 ==========
    bool win_sign;
    bool lose_sign;
    bool catched;

    // ========== 생성자 ==========
    GameState() {
        reset();
    }

    void reset() {
        // 맵 초기화
        for (int i = 0; i < MAP_SIZE; i++) {
            for (int j = 0; j < MAP_SIZE; j++) {
                wall[i][j] = 0;
                sc[i][j] = 0;
                junc[i][j] = 0;
                deadend[i][j] = 0;
            }
        }

        // 엔티티 초기화
        mouse = Position(10, 10);
        mouse_last = Position(10, 10);

        for (int i = 0; i < Config::NUM_CATS; i++) {
            cats[i] = Entity();
        }
        for (int i = 0; i < Config::NUM_MOVBC; i++) {
            movbc[i] = Entity();
        }
        for (int i = 0; i < Config::NUM_CRZBC; i++) {
            crzbc[i] = Entity();
        }

        // 상태 초기화
        score = 0;
        life = Config::DEFAULT_LIFE;
        step = 0;
        step_limit = Config::DEFAULT_STEP_LIMIT;
        run = 0;
        func_chance = Config::DEFAULT_FUNC_CHANCE;
        red_zone = Config::DEFAULT_RED_ZONE;

        // 플래그 초기화
        win_sign = false;
        lose_sign = false;
        catched = false;
    }

    // ========== Level 3 초기화 (Python과 동일) ==========
    void init_level3() {
        reset();

        // 벽 데이터 (Python lightweight_simulator.py에서 복사)
        static const int8_t WALL_DATA[11][11] = {
            {0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0},
            {0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0},
            {0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0},
            {0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0},
            {0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1},
            {0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0},
            {0, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0}
        };

        // 작은 치즈 데이터
        static const int8_t SC_DATA[11][11] = {
            {1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1},
            {1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1},
            {1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1},
            {1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1},
            {1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1},
            {1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1},
            {1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1},
            {1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1},
            {0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0},
            {1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1},
            {1, 0, 0, 1, 1, 1, 1, 1, 0, 0, 1}
        };

        // 교차로 데이터
        static const int8_t JUNC_DATA[11][11] = {
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 1, 1, 0, 1, 1, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}
        };

        // 막다른 길 데이터 (Python과 동일: 오직 3개 위치만)
        // (0,5), (10,0), (10,10)
        static const int8_t DEADEND_DATA[11][11] = {
            {0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0},  // row 0: (0,5)만
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1}   // row 10: (10,0), (10,10)
        };

        // 데이터 복사
        for (int i = 0; i < MAP_SIZE; i++) {
            for (int j = 0; j < MAP_SIZE; j++) {
                wall[i][j] = WALL_DATA[i][j];
                sc[i][j] = SC_DATA[i][j];
                junc[i][j] = JUNC_DATA[i][j];
                deadend[i][j] = DEADEND_DATA[i][j];
            }
        }

        // 마우스 초기 위치
        mouse = Position(10, 10);
        mouse_last = Position(10, 10);
        sc[10][10] = 0;  // 시작 위치 치즈 제거

        // 고양이 초기 위치
        cats[0].pos = Position(2, 2);
        cats[0].last_pos = Position(2, 2);
        cats[0].direction = Direction::DOWN;
        cats[0].active = true;

        cats[1].pos = Position(5, 5);
        cats[1].last_pos = Position(5, 5);
        cats[1].direction = Direction::RIGHT;
        cats[1].active = true;

        // 이동 빅치즈 초기 위치
        movbc[0].pos = Position(1, 5);
        movbc[0].last_pos = Position(1, 5);
        movbc[0].active = true;

        movbc[1].pos = Position(7, 5);
        movbc[1].last_pos = Position(7, 5);
        movbc[1].active = true;

        // 미친 빅치즈 (초기 위치는 시뮬레이션에서 랜덤 설정)
        crzbc[0].pos = Position(0, 3);
        crzbc[0].last_pos = Position(0, 3);
        crzbc[0].direction = Direction::RIGHT;
        crzbc[0].active = true;

        crzbc[1].pos = Position(10, 7);
        crzbc[1].last_pos = Position(10, 7);
        crzbc[1].direction = Direction::LEFT;
        crzbc[1].active = true;
    }

    // ========== 남은 치즈 개수 ==========
    int count_remaining_cheese() const {
        int count = 0;
        for (int i = 0; i < MAP_SIZE; i++) {
            for (int j = 0; j < MAP_SIZE; j++) {
                count += sc[i][j];
            }
        }
        return count;
    }
};

} // namespace simulator
