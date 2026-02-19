#include "simulator.hpp"
#include <cmath>
#include <algorithm>

#ifdef DEBUG_IF
#include <iostream>
#endif

#ifdef USE_OPENMP
#include <omp.h>
#endif

namespace simulator {

// 정적 멤버 정의
bool Simulator::global_cache_enabled_ = false;

// ============================================================
// 생성자
// ============================================================
Simulator::Simulator(int level) : level_(level), rng_(std::random_device{}()) {
    reset();
}

void Simulator::reset() {
    if (level_ == 3) {
        state_.init_level3();
    } else {
        state_.reset();
    }
}

void Simulator::restore_state(const GameState& state) {
    state_ = state;
}

// ============================================================
// BFS 거리 맵 캐시 구현 (전역 공유)
// ============================================================

DistanceMap GlobalDistanceCache::compute_distance_map(
    const std::array<std::array<int8_t, MAP_SIZE>, MAP_SIZE>& wall,
    int start_row, int start_col
) const {
    DistanceMap dist_map;

    // 초기화: 벽은 -1, 나머지는 0
    for (int i = 0; i < MAP_SIZE; i++) {
        for (int j = 0; j < MAP_SIZE; j++) {
            dist_map[i][j] = wall[i][j] ? -1 : 0;
        }
    }

    // 시작점
    dist_map[start_row][start_col] = 1;

    // BFS
    std::deque<Position> queue;
    queue.push_back(Position{static_cast<int8_t>(start_row), static_cast<int8_t>(start_col)});

    while (!queue.empty()) {
        Position curr = queue.front();
        queue.pop_front();

        int16_t curr_dist = dist_map[curr.x][curr.y];

        // 4방향 탐색
        for (int dir = 0; dir < Direction::COUNT; dir++) {
            Position next = curr.move(dir);
            if (next.is_valid() && dist_map[next.x][next.y] == 0) {
                dist_map[next.x][next.y] = curr_dist + 1;
                queue.push_back(next);
            }
        }
    }

    return dist_map;
}

void GlobalDistanceCache::initialize(
    const std::array<std::array<int8_t, MAP_SIZE>, MAP_SIZE>& wall
) {
    // 121개 위치에 대한 거리 맵을 사전 계산
    cache_.resize(MAP_SIZE * MAP_SIZE);

    #ifdef USE_OPENMP
    #pragma omp parallel for schedule(static)
    #endif
    for (int pos = 0; pos < MAP_SIZE * MAP_SIZE; pos++) {
        int row = pos / MAP_SIZE;
        int col = pos % MAP_SIZE;
        cache_[pos] = compute_distance_map(wall, row, col);
    }

    initialized_ = true;
}

void Simulator::initialize_cache() {
    GlobalDistanceCache::instance().initialize(state_.wall);
    global_cache_enabled_ = true;
}

// ============================================================
// 이동 함수
// ============================================================
bool Simulator::movable(const Position& pos, int dir) const {
    Position next = pos.move(dir);
    if (!next.is_valid()) return false;
    return state_.wall[next.x][next.y] == 0;
}

Position Simulator::move_pos(const Position& pos, int dir) const {
    Position next = pos.move(dir);
    // 경계 클램핑
    next.x = std::max(int8_t(0), std::min(int8_t(MAP_SIZE - 1), next.x));
    next.y = std::max(int8_t(0), std::min(int8_t(MAP_SIZE - 1), next.y));
    return next;
}

// ============================================================
// BFS 거리 맵 (전역 캐시 사용)
// ============================================================
DistanceMap Simulator::create_distance_map(const Position& target) const {
    // 전역 캐시가 활성화되어 있고 초기화되어 있으면 캐시에서 반환
    if (global_cache_enabled_ && GlobalDistanceCache::instance().is_initialized()) {
        return GlobalDistanceCache::instance().get(target.x, target.y);
    }

    // 캐시가 없으면 직접 계산
    DistanceMap dist_map;

    // 초기화: 벽은 -1, 나머지는 0
    for (int i = 0; i < MAP_SIZE; i++) {
        for (int j = 0; j < MAP_SIZE; j++) {
            dist_map[i][j] = state_.wall[i][j] ? -1 : 0;
        }
    }

    // 시작점
    dist_map[target.x][target.y] = 1;

    // BFS
    std::deque<Position> queue;
    queue.push_back(target);

    while (!queue.empty()) {
        Position curr = queue.front();
        queue.pop_front();

        int16_t curr_dist = dist_map[curr.x][curr.y];

        // 4방향 탐색
        for (int dir = 0; dir < Direction::COUNT; dir++) {
            Position next = curr.move(dir);
            if (next.is_valid() && dist_map[next.x][next.y] == 0) {
                dist_map[next.x][next.y] = curr_dist + 1;
                queue.push_back(next);
            }
        }
    }

    return dist_map;
}

// ============================================================
// 프로그램 파싱 (Python _parse_program과 동일)
// ============================================================
ParsedProgram Simulator::parse_program(const std::vector<int>& program) {
    ParsedProgram result;
    int first_func_id = -1;
    int second_func_id = -1;

    for (int token : program) {
        if (token == Token::END) {
            break;
        }
        if (token == Token::EMPTY) {
            continue;
        }

        // 함수 라이브러리 ID (113-998)
        if (Token::is_func_lib(token)) {
            if (first_func_id < 0) {
                // 첫 번째 함수
                first_func_id = token;
                result.func1 = func_lib_.get_function(token);
                result.main_cmd.push_back(Token::FUNC_F1);
            } else if (token == first_func_id) {
                // 같은 함수 재사용
                result.main_cmd.push_back(Token::FUNC_F1);
            } else if (second_func_id < 0) {
                // 두 번째 함수
                second_func_id = token;
                result.func2 = func_lib_.get_function(token);
                result.main_cmd.push_back(Token::FUNC_F2);
            } else if (token == second_func_id) {
                // 같은 함수 재사용
                result.main_cmd.push_back(Token::FUNC_F2);
            }
            // 세 번째 이상 다른 함수는 무시
        } else {
            result.main_cmd.push_back(token);
        }
    }

    return result;
}

// ============================================================
// 액션 변환 (Python _get_mouse_actions과 동일)
// ============================================================
ActionResult Simulator::get_mouse_actions(
    const std::vector<int>& command,
    const std::vector<int>& func1,
    const std::vector<int>& func2,
    const GameState& sim_state
) {
    ActionResult result;
    int action_idx = 0;
    GameState temp_state = sim_state;

    process_commands(command, func1, func2, temp_state,
                     result.actions, result.wall_collisions, action_idx);

    return result;
}

void Simulator::process_commands(
    const std::vector<int>& commands,
    const std::vector<int>& func1,
    const std::vector<int>& func2,
    GameState& sim_state,
    std::vector<int>& actions,
    std::set<int>& wall_collisions,
    int& action_idx
) {
    int need_next = 0;  // 0: 일반, 110: LOOP 수 대기, 5: IF 수 대기
    int pc = 0;         // 0: 일반, 110: LOOP, 5: IF
    int n_iter = 0;

    for (size_t i = 0; i < commands.size(); i++) {
        int cmd = commands[i];

        if (cmd == Token::END) break;
        if (cmd == Token::EMPTY) continue;

        // 함수 호출 처리
        if (cmd == Token::FUNC_F1 && !func1.empty()) {
            process_commands(func1, func1, func2, sim_state,
                           actions, wall_collisions, action_idx);
            continue;
        }
        if (cmd == Token::FUNC_F2 && !func2.empty()) {
            process_commands(func2, func1, func2, sim_state,
                           actions, wall_collisions, action_idx);
            continue;
        }

        // 상태 머신
        if (need_next == 0) {
            if (Token::is_direction(cmd)) {
                // 단일 방향 이동
                if (movable(sim_state.mouse, cmd)) {
                    sim_state.mouse = move_pos(sim_state.mouse, cmd);
                    actions.push_back(cmd);
                } else {
                    wall_collisions.insert(action_idx);
                    actions.push_back(cmd);
                }
                action_idx++;
            } else if (cmd == Token::LOOP) {
                need_next = Token::LOOP;
            } else if (cmd == Token::IF) {
                need_next = Token::IF;
            }
        } else if (need_next == Token::LOOP) {
            // LOOP 반복 횟수
            if (Token::is_num(cmd)) {
                n_iter = Token::get_num_value(cmd);
                pc = Token::LOOP;
                need_next = cmd;  // 방향 대기
            }
        } else if (need_next == Token::IF) {
            // IF 반복 횟수 (Python: range(101, 108) = 1-7만 허용)
            if (Token::is_if_num(cmd)) {
                n_iter = Token::get_num_value(cmd);
                pc = Token::IF;
                need_next = cmd;  // 방향 대기
            } else {
                // 유효하지 않은 숫자면 IF 상태 유지 (Python과 동일하게 후속 명령어 무시)
                pc = Token::IF;
                need_next = cmd;  // 유효하지 않은 값으로 유지 → IF 실행 조건 불충족
            }
        } else if (pc == Token::LOOP && Token::is_direction(cmd)) {
            // LOOP 실행
            for (int j = 0; j < n_iter; j++) {
                if (movable(sim_state.mouse, cmd)) {
                    sim_state.mouse = move_pos(sim_state.mouse, cmd);
                    actions.push_back(cmd);
                } else {
                    wall_collisions.insert(action_idx);
                    actions.push_back(cmd);
                }
                action_idx++;
            }
            need_next = 0;
            pc = 0;
        } else if (pc == Token::IF && Token::is_if_num(need_next) && Token::is_direction(cmd)) {
            // IF 실행 (교차로까지 이동) - need_next가 유효한 IF 숫자(101-107)여야 함
            int remaining = n_iter;
            #ifdef DEBUG_IF
            std::cerr << "[IF] Starting: n_iter=" << n_iter << ", dir=" << cmd
                      << ", mouse=(" << (int)sim_state.mouse.x << "," << (int)sim_state.mouse.y << ")\n";
            #endif
            while (remaining > 0) {
                bool can_move = movable(sim_state.mouse, cmd);
                #ifdef DEBUG_IF
                std::cerr << "[IF] remaining=" << remaining << ", movable=" << can_move << "\n";
                #endif
                if (can_move) {
                    sim_state.mouse = move_pos(sim_state.mouse, cmd);
                    actions.push_back(cmd);
                    action_idx++;

                    // 교차로 도달 시 remaining 감소
                    if (sim_state.junc[sim_state.mouse.x][sim_state.mouse.y]) {
                        remaining--;
                    }
                    #ifdef DEBUG_IF
                    std::cerr << "[IF] Moved to (" << (int)sim_state.mouse.x << "," << (int)sim_state.mouse.y
                              << "), junc=" << (int)sim_state.junc[sim_state.mouse.x][sim_state.mouse.y] << "\n";
                    #endif
                } else {
                    // 벽에 막히면 종료 (Python과 동일하게 액션 추가 없음)
                    #ifdef DEBUG_IF
                    std::cerr << "[IF] Wall hit, stopping (no action added)\n";
                    #endif
                    break;
                }
            }
            need_next = 0;
            pc = 0;
        }
    }
}

// ============================================================
// 고양이 AI (Python 고양이 이동 로직과 동일)
// ============================================================
void Simulator::move_cats(GameState& sim_state, const DistanceMap& dist_map) {
    for (auto& cat : sim_state.cats) {
        if (!cat.active) continue;
        move_single_cat(cat, sim_state, dist_map);
    }
}

void Simulator::move_single_cat(Entity& cat, const GameState& sim_state, const DistanceMap& dist_map) {
    cat.last_pos = cat.pos;

    // 막다른 길이면 정지
    if (sim_state.deadend[cat.pos.x][cat.pos.y]) {
        return;
    }

    int16_t my_dist = dist_map[cat.pos.x][cat.pos.y];

    // Red Zone: 마우스로부터 도망
    if (my_dist > 0 && my_dist <= sim_state.red_zone) {
        int best_dir = -1;
        int16_t max_dist = my_dist;

        for (int dir = 0; dir < Direction::COUNT; dir++) {
            Position next = cat.pos.move(dir);
            if (!next.is_valid()) continue;
            if (sim_state.wall[next.x][next.y]) continue;

            int16_t next_dist = dist_map[next.x][next.y];
            if (next_dist > max_dist) {
                max_dist = next_dist;
                best_dir = dir;
            }
        }

        if (best_dir >= 0) {
            cat.pos = cat.pos.move(best_dir);
            cat.direction = best_dir;
            return;
        }
    }

    // 교차로: 랜덤 방향 (뒤로 가지 않음)
    if (sim_state.junc[cat.pos.x][cat.pos.y]) {
        std::vector<int> valid_dirs;
        int back_dir = Direction::OPPOSITE[cat.direction];

        for (int dir = 0; dir < Direction::COUNT; dir++) {
            if (dir == back_dir) continue;
            Position next = cat.pos.move(dir);
            if (next.is_valid() && !sim_state.wall[next.x][next.y]) {
                valid_dirs.push_back(dir);
            }
        }

        if (!valid_dirs.empty()) {
            std::uniform_int_distribution<> dist(0, valid_dirs.size() - 1);
            int chosen = valid_dirs[dist(rng_)];
            cat.pos = cat.pos.move(chosen);
            cat.direction = chosen;
            return;
        }
    }

    // 현재 방향 유지
    Position next = cat.pos.move(cat.direction);
    if (next.is_valid() && !sim_state.wall[next.x][next.y]) {
        cat.pos = next;
        return;
    }

    // 랜덤 방향
    for (int tries = 0; tries < Config::MAX_RANDOM_TRIES; tries++) {
        std::uniform_int_distribution<> dist(0, Direction::COUNT - 1);
        int dir = dist(rng_);
        next = cat.pos.move(dir);
        if (next.is_valid() && !sim_state.wall[next.x][next.y]) {
            cat.pos = next;
            cat.direction = dir;
            return;
        }
    }
}

// ============================================================
// 빅치즈 이동
// ============================================================
void Simulator::move_movbc(GameState& sim_state) {
    for (auto& bc : sim_state.movbc) {
        if (!bc.active) continue;
        bc.last_pos = bc.pos;

        // 랜덤 방향으로 이동 시도
        for (int tries = 0; tries < Config::MAX_RANDOM_TRIES; tries++) {
            std::uniform_int_distribution<> dist(0, Direction::COUNT - 1);
            int dir = dist(rng_);
            Position next = bc.pos.move(dir);
            if (next.is_valid() && !sim_state.wall[next.x][next.y]) {
                bc.pos = next;
                break;
            }
        }
    }
}

void Simulator::move_crzbc(GameState& sim_state, const DistanceMap& dist_map) {
    for (auto& bc : sim_state.crzbc) {
        if (!bc.active) continue;
        bc.last_pos = bc.pos;

        // 고양이와 유사한 로직
        if (sim_state.deadend[bc.pos.x][bc.pos.y]) {
            continue;
        }

        // 교차로: 랜덤 방향
        if (sim_state.junc[bc.pos.x][bc.pos.y]) {
            std::vector<int> valid_dirs;
            int back_dir = Direction::OPPOSITE[bc.direction];

            for (int dir = 0; dir < Direction::COUNT; dir++) {
                if (dir == back_dir) continue;
                Position next = bc.pos.move(dir);
                if (next.is_valid() && !sim_state.wall[next.x][next.y]) {
                    valid_dirs.push_back(dir);
                }
            }

            if (!valid_dirs.empty()) {
                std::uniform_int_distribution<> dist_rand(0, valid_dirs.size() - 1);
                int chosen = valid_dirs[dist_rand(rng_)];
                bc.pos = bc.pos.move(chosen);
                bc.direction = chosen;
                continue;
            }
        }

        // 현재 방향 유지
        Position next = bc.pos.move(bc.direction);
        if (next.is_valid() && !sim_state.wall[next.x][next.y]) {
            bc.pos = next;
            continue;
        }

        // 랜덤 방향
        for (int tries = 0; tries < Config::MAX_RANDOM_TRIES; tries++) {
            std::uniform_int_distribution<> dist_rand(0, Direction::COUNT - 1);
            int dir = dist_rand(rng_);
            next = bc.pos.move(dir);
            if (next.is_valid() && !sim_state.wall[next.x][next.y]) {
                bc.pos = next;
                bc.direction = dir;
                break;
            }
        }
    }
}

// ============================================================
// Crossing 감지
// ============================================================
bool Simulator::check_crossing(const Position& p1, const Position& p1_last,
                                const Position& p2, const Position& p2_last) const {
    return (p1 == p2_last && p2 == p1_last);
}

// ============================================================
// Pre-calculate cat actions (exe3.py _get_cats_direct_actions0 - FLEE mode)
// ============================================================
std::array<std::vector<int>, Config::NUM_CATS> Simulator::pre_calculate_cat_actions(
    const std::vector<int>& mouse_actions, const GameState& sim_state)
{
    std::array<std::vector<int>, Config::NUM_CATS> cat_actions;

    // Virtual state for pre-calculation
    std::array<Position, Config::NUM_CATS> virtual_cats;
    std::array<int, Config::NUM_CATS> virtual_dirs;

    for (int i = 0; i < Config::NUM_CATS; i++) {
        virtual_cats[i] = sim_state.cats[i].pos;
        virtual_dirs[i] = sim_state.cats[i].direction;
    }

    int n_steps = static_cast<int>(mouse_actions.size());

    // RANDOM mode (exe3.py _get_cats_direct_actions): no flee, no mouse tracking
    for (int step = 0; step < n_steps; step++) {
        for (int i = 0; i < Config::NUM_CATS; i++) {
            Position& cat_pos = virtual_cats[i];
            int& cat_dir = virtual_dirs[i];

            // Junction: random direction (no turning back)
            if (sim_state.junc[cat_pos.x][cat_pos.y]) {
                bool found = false;
                for (int tries = 0; tries < Config::MAX_RANDOM_TRIES; tries++) {
                    std::uniform_int_distribution<> dist(0, Direction::COUNT - 1);
                    int new_dir = dist(rng_);
                    if (new_dir == Direction::OPPOSITE[cat_dir]) continue;
                    Position next = cat_pos.move(new_dir);
                    if (next.is_valid() && !sim_state.wall[next.x][next.y]) {
                        cat_pos = next;
                        cat_dir = new_dir;
                        cat_actions[i].push_back(new_dir);
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    cat_actions[i].push_back(cat_dir >= 0 && cat_dir < Direction::COUNT ? cat_dir : 0);
                }
            }
            // Continue in current direction
            else if (movable(cat_pos, cat_dir)) {
                cat_pos = move_pos(cat_pos, cat_dir);
                cat_actions[i].push_back(cat_dir);
            }
            // Blocked: random direction
            else {
                bool found = false;
                for (int tries = 0; tries < Config::MAX_RANDOM_TRIES; tries++) {
                    std::uniform_int_distribution<> dist(0, Direction::COUNT - 1);
                    int new_dir = dist(rng_);
                    Position next = cat_pos.move(new_dir);
                    if (next.is_valid() && !sim_state.wall[next.x][next.y]) {
                        cat_pos = next;
                        cat_dir = new_dir;
                        cat_actions[i].push_back(new_dir);
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    cat_actions[i].push_back(cat_dir >= 0 && cat_dir < Direction::COUNT ? cat_dir : 0);
                }
            }
        }
    }

    return cat_actions;
}

// ============================================================
// Pre-calculate crzbc actions (exe3.py _get_crzbc_actions matching)
// ============================================================
std::array<std::vector<int>, Config::NUM_CRZBC> Simulator::pre_calculate_crzbc_actions(
    int n_moves, const GameState& sim_state)
{
    std::array<std::vector<int>, Config::NUM_CRZBC> crzbc_actions;

    std::array<Position, Config::NUM_CRZBC> virtual_crzbc;
    std::array<int, Config::NUM_CRZBC> virtual_dirs;

    for (int i = 0; i < Config::NUM_CRZBC; i++) {
        virtual_crzbc[i] = sim_state.crzbc[i].pos;
        virtual_dirs[i] = sim_state.crzbc[i].direction;
    }

    for (int step = 0; step < n_moves; step++) {
        for (int i = 0; i < Config::NUM_CRZBC; i++) {
            if (!sim_state.crzbc[i].active) continue;

            Position& pos = virtual_crzbc[i];
            int& dir = virtual_dirs[i];

            if (!pos.is_valid()) continue;

            // Junction: random (no turning back)
            if (sim_state.junc[pos.x][pos.y]) {
                bool found = false;
                for (int tries = 0; tries < Config::MAX_RANDOM_TRIES; tries++) {
                    std::uniform_int_distribution<> dist(0, Direction::COUNT - 1);
                    int new_dir = dist(rng_);
                    if (new_dir == Direction::OPPOSITE[dir]) continue;
                    Position next = pos.move(new_dir);
                    if (next.is_valid() && !sim_state.wall[next.x][next.y]) {
                        pos = next;
                        dir = new_dir;
                        crzbc_actions[i].push_back(new_dir);
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    crzbc_actions[i].push_back(dir >= 0 && dir < Direction::COUNT ? dir : 0);
                }
            }
            // Continue in current direction
            else if (movable(pos, dir)) {
                pos = move_pos(pos, dir);
                crzbc_actions[i].push_back(dir);
            }
            // Random direction
            else {
                bool found = false;
                for (int tries = 0; tries < Config::MAX_RANDOM_TRIES; tries++) {
                    std::uniform_int_distribution<> dist(0, Direction::COUNT - 1);
                    int new_dir = dist(rng_);
                    Position next = pos.move(new_dir);
                    if (next.is_valid() && !sim_state.wall[next.x][next.y]) {
                        pos = next;
                        dir = new_dir;
                        crzbc_actions[i].push_back(new_dir);
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    crzbc_actions[i].push_back(dir >= 0 && dir < Direction::COUNT ? dir : 0);
                }
            }
        }
    }

    return crzbc_actions;
}

// ============================================================
// 시뮬레이션 (exe3.py running_op 매칭)
// ============================================================
float Simulator::simulate_program(const std::vector<int>& program) {
    // 가상 상태 복사
    GameState sim_state = state_;
    int virtual_score = state_.score;
    int virtual_life = state_.life;

    // 1. 프로그램 파싱
    ParsedProgram parsed = parse_program(program);

    // 2. 액션 변환
    ActionResult action_result = get_mouse_actions(
        parsed.main_cmd, parsed.func1, parsed.func2, sim_state
    );

    // 상태 재설정 (액션 변환에서 수정됨)
    sim_state = state_;

    // command_length: 프로그램 토큰 수 (END 포함, Python len(command) 매칭)
    int command_length = 0;
    for (int token : program) {
        command_length++;
        if (token == Token::END) break;
    }

    // 3. Pre-calculate entity actions (exe3.py style)
    auto cat_actions = pre_calculate_cat_actions(action_result.actions, sim_state);
    auto crzbc_actions = pre_calculate_crzbc_actions(command_length, sim_state);

    // 4. 시뮬레이션 루프
    for (size_t itr = 0; itr < action_result.actions.size(); itr++) {
        int action = action_result.actions[itr];

        // 1. Wall collision
        if (action_result.wall_collisions.count(itr)) {
            virtual_score += Score::WALL_COLLISION;
        }

        // 2. Mouse moves
        sim_state.mouse_last = sim_state.mouse;
        if (movable(sim_state.mouse, action)) {
            sim_state.mouse = move_pos(sim_state.mouse, action);
            sim_state.step++;
        }

        // 3. Cat1 (naughty) moves every step
        if (itr < cat_actions[1].size()) {
            if (movable(sim_state.cats[1].pos, cat_actions[1][itr])) {
                Position new_pos = move_pos(sim_state.cats[1].pos, cat_actions[1][itr]);
                // Cat-cat collision prevention
                if (new_pos != sim_state.cats[0].pos) {
                    sim_state.cats[1].last_pos = sim_state.cats[1].pos;
                    sim_state.cats[1].pos = new_pos;
                }
            }
        }

        // 4. Cat0 (dummy) moves only for command_length steps
        if ((int)itr < command_length && itr < cat_actions[0].size()) {
            if (movable(sim_state.cats[0].pos, cat_actions[0][itr])) {
                Position new_pos = move_pos(sim_state.cats[0].pos, cat_actions[0][itr]);
                // Cat-cat collision prevention
                if (new_pos != sim_state.cats[1].pos) {
                    sim_state.cats[0].last_pos = sim_state.cats[0].pos;
                    sim_state.cats[0].pos = new_pos;
                }
            }
        }

        // 5. Crzbc moves (pre-calculated, for command_length steps)
        for (int j = 0; j < Config::NUM_CRZBC; j++) {
            if (!sim_state.crzbc[j].active) continue;
            if (itr < crzbc_actions[j].size()) {
                if (movable(sim_state.crzbc[j].pos, crzbc_actions[j][itr])) {
                    Position new_pos = move_pos(sim_state.crzbc[j].pos, crzbc_actions[j][itr]);
                    // Collision check with cats and other crzbc
                    bool collision = false;
                    for (int c = 0; c < Config::NUM_CATS; c++) {
                        if (new_pos == sim_state.cats[c].pos) {
                            collision = true;
                            break;
                        }
                    }
                    for (int k = 0; k < Config::NUM_CRZBC; k++) {
                        if (k != j && sim_state.crzbc[k].active && new_pos == sim_state.crzbc[k].pos) {
                            collision = true;
                            break;
                        }
                    }
                    if (!collision) {
                        sim_state.crzbc[j].pos = new_pos;
                    }
                }
            }
        }

        // 6. Cat collision check AFTER movement (no break - both cats can catch)
        bool catched = false;
        for (int ci = 0; ci < Config::NUM_CATS; ci++) {
            if (!sim_state.cats[ci].active) continue;
            if (sim_state.mouse == sim_state.cats[ci].pos ||
                check_crossing(sim_state.mouse, sim_state.mouse_last,
                               sim_state.cats[ci].pos, sim_state.cats[ci].last_pos)) {
                virtual_score += Score::CAT_COLLISION;
                virtual_life--;
                catched = true;
                // No break: both cats can catch in same step
            }
        }

        // 7. movbc collection (NO movement - stationary)
        for (auto& bc : sim_state.movbc) {
            if (!bc.active) continue;
            if (sim_state.mouse == bc.pos) {
                bc.active = false;
                virtual_score += Score::BIG_CHEESE;
            }
        }

        // 8. crzbc collection
        for (auto& bc : sim_state.crzbc) {
            if (!bc.active) continue;
            if (sim_state.mouse == bc.pos) {
                bc.active = false;
                virtual_score += Score::BIG_CHEESE;
            }
        }

        // 9. SC collection
        if (sim_state.sc[sim_state.mouse.x][sim_state.mouse.y]) {
            sim_state.sc[sim_state.mouse.x][sim_state.mouse.y] = 0;
            virtual_score += Score::SMALL_CHEESE;
        }

        // 10. Win/lose check (exe3.py order: life→sc→step)
        if (virtual_life <= 0) {
            break;
        }
        if (sim_state.count_remaining_cheese() == 0) {
            sim_state.win_sign = true;
            int victory_bonus = sim_state.run * 10 + sim_state.step;
            virtual_score += victory_bonus;
            break;
        }
        if (sim_state.step >= sim_state.step_limit) {
            break;
        }

        // 11. Catched: break this run
        if (catched) {
            break;
        }
    }

    // 루프 후 승리 체크 (루프가 정상 종료된 경우)
    if (!sim_state.win_sign && sim_state.count_remaining_cheese() == 0) {
        sim_state.win_sign = true;
        int victory_bonus = sim_state.run * 10 + sim_state.step;
        virtual_score += victory_bonus;
    }

    return static_cast<float>(virtual_score);
}

float Simulator::simulate_program_and_apply(const std::vector<int>& program) {
    float score = simulate_program(program);
    // 상태는 simulate_program에서 변경되지 않음 (가상 상태 사용)
    // 실제 적용이 필요하면 별도 구현
    return score;
}

// ============================================================
// 배치 시뮬레이션 (OpenMP 병렬)
// ============================================================
std::vector<float> batch_simulate(
    const std::vector<std::vector<int>>& programs,
    const GameState& initial_state,
    int num_threads
) {
    std::vector<float> results(programs.size());

#ifdef USE_OPENMP
    if (num_threads <= 0) {
        num_threads = omp_get_max_threads();
    }

    #pragma omp parallel for num_threads(num_threads)
    for (size_t i = 0; i < programs.size(); i++) {
        Simulator sim(3);
        sim.restore_state(initial_state);
        results[i] = sim.simulate_program(programs[i]);
    }
#else
    // 시리얼 버전
    for (size_t i = 0; i < programs.size(); i++) {
        Simulator sim(3);
        sim.restore_state(initial_state);
        results[i] = sim.simulate_program(programs[i]);
    }
#endif

    return results;
}

} // namespace simulator
