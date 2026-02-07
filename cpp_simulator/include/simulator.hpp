#pragma once

#include <vector>
#include <deque>
#include <random>
#include <algorithm>
#include <set>
#include "constants.hpp"
#include "game_state.hpp"
#include "function_library.hpp"

namespace simulator {

// ============================================================
// 거리 맵 타입 (BFS 결과)
// ============================================================
using DistanceMap = std::array<std::array<int16_t, MAP_SIZE>, MAP_SIZE>;

// ============================================================
// BFS 거리 맵 캐시 (전역 공유, 스레드 안전)
// ============================================================
class GlobalDistanceCache {
public:
    // 싱글톤 인스턴스
    static GlobalDistanceCache& instance() {
        static GlobalDistanceCache inst;
        return inst;
    }

    // 벽 정보를 받아서 모든 위치의 거리 맵을 계산
    void initialize(const std::array<std::array<int8_t, MAP_SIZE>, MAP_SIZE>& wall);

    // 특정 위치의 거리 맵 조회 (O(1))
    const DistanceMap& get(int row, int col) const {
        return cache_[row * MAP_SIZE + col];
    }

    bool is_initialized() const { return initialized_; }
    void clear() { initialized_ = false; cache_.clear(); }

private:
    GlobalDistanceCache() = default;
    GlobalDistanceCache(const GlobalDistanceCache&) = delete;
    GlobalDistanceCache& operator=(const GlobalDistanceCache&) = delete;

    std::vector<DistanceMap> cache_;  // 121개의 거리 맵
    bool initialized_ = false;

    // 단일 위치에 대한 BFS 거리 맵 계산
    DistanceMap compute_distance_map(
        const std::array<std::array<int8_t, MAP_SIZE>, MAP_SIZE>& wall,
        int start_row, int start_col
    ) const;
};

// ============================================================
// 파싱된 프로그램
// ============================================================
struct ParsedProgram {
    std::vector<int> main_cmd;
    std::vector<int> func1;
    std::vector<int> func2;
};

// ============================================================
// 액션 결과
// ============================================================
struct ActionResult {
    std::vector<int> actions;       // 방향 액션 리스트
    std::set<int> wall_collisions;  // 벽 충돌 인덱스
};

// ============================================================
// 시뮬레이터 클래스
// ============================================================
class Simulator {
public:
    // 생성자
    explicit Simulator(int level = 3);

    // ========== 핵심 API ==========

    // 프로그램 실행 후 점수 반환 (상태 변경 안 함)
    float simulate_program(const std::vector<int>& program);

    // 프로그램 실행 후 상태 적용
    float simulate_program_and_apply(const std::vector<int>& program);

    // ========== 상태 관리 ==========

    void restore_state(const GameState& state);
    GameState get_state() const { return state_; }
    void reset();

    // ========== 캐시 관리 (전역 공유) ==========

    // 현재 벽 정보로 전역 캐시 초기화 (한 번만 호출하면 됨)
    void initialize_cache();
    static void enable_global_cache() { global_cache_enabled_ = true; }
    static void disable_global_cache() { global_cache_enabled_ = false; }
    static bool is_cache_initialized() { return GlobalDistanceCache::instance().is_initialized(); }
    static bool is_cache_enabled() { return global_cache_enabled_; }

    // ========== 속성 접근 ==========

    int get_score() const { return state_.score; }
    int get_life() const { return state_.life; }
    int get_step() const { return state_.step; }
    bool is_win() const { return state_.win_sign; }
    bool is_lose() const { return state_.lose_sign; }

private:
    GameState state_;
    FunctionLibrary func_lib_;
    std::mt19937 rng_;
    int level_;

    // 전역 캐시 활성화 플래그 (static)
    static bool global_cache_enabled_;

    // ========== 이동 함수 ==========

    bool movable(const Position& pos, int dir) const;
    Position move_pos(const Position& pos, int dir) const;

    // ========== BFS 거리 맵 ==========

    DistanceMap create_distance_map(const Position& target) const;

    // ========== 프로그램 파싱 ==========

    ParsedProgram parse_program(const std::vector<int>& program);

    // ========== 액션 변환 ==========

    ActionResult get_mouse_actions(
        const std::vector<int>& command,
        const std::vector<int>& func1,
        const std::vector<int>& func2,
        const GameState& sim_state
    );

    // 재귀적 액션 처리
    void process_commands(
        const std::vector<int>& commands,
        const std::vector<int>& func1,
        const std::vector<int>& func2,
        GameState& sim_state,
        std::vector<int>& actions,
        std::set<int>& wall_collisions,
        int& action_idx
    );

    // ========== 고양이 AI ==========

    void move_cats(GameState& sim_state, const DistanceMap& dist_map);
    void move_single_cat(Entity& cat, const GameState& sim_state, const DistanceMap& dist_map);

    // ========== 빅치즈 이동 ==========

    void move_movbc(GameState& sim_state);
    void move_crzbc(GameState& sim_state, const DistanceMap& dist_map);

    // ========== 충돌 감지 ==========

    // Crossing 감지 (서로 교차)
    bool check_crossing(const Position& p1, const Position& p1_last,
                        const Position& p2, const Position& p2_last) const;
};

// ============================================================
// 배치 시뮬레이션 (병렬)
// ============================================================
std::vector<float> batch_simulate(
    const std::vector<std::vector<int>>& programs,
    const GameState& initial_state,
    int num_threads = 0  // 0 = 자동 감지
);

} // namespace simulator
