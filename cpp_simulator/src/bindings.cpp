#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "simulator.hpp"
#include "game_state.hpp"
#include "constants.hpp"

namespace py = pybind11;

// ============================================================
// Python dict → GameState 변환 헬퍼
// ============================================================
simulator::GameState dict_to_state(py::dict state_dict) {
    simulator::GameState state;

    // mouse
    auto mouse = state_dict["mouse"].cast<std::vector<int>>();
    state.mouse.x = mouse[0];
    state.mouse.y = mouse[1];

    // mouse_last_pos (옵션)
    if (state_dict.contains("mouse_last_pos")) {
        auto ml = state_dict["mouse_last_pos"].cast<std::vector<int>>();
        state.mouse_last.x = ml[0];
        state.mouse_last.y = ml[1];
    } else {
        state.mouse_last = state.mouse;
    }

    // cat
    auto cat = state_dict["cat"].cast<std::vector<std::vector<int>>>();
    for (size_t i = 0; i < cat.size() && i < simulator::Config::NUM_CATS; i++) {
        state.cats[i].pos.x = cat[i][0];
        state.cats[i].pos.y = cat[i][1];
        state.cats[i].last_pos = state.cats[i].pos;
        state.cats[i].active = true;
    }

    // cat_last_pos (옵션)
    if (state_dict.contains("cat_last_pos")) {
        auto cl = state_dict["cat_last_pos"].cast<std::vector<std::vector<int>>>();
        for (size_t i = 0; i < cl.size() && i < simulator::Config::NUM_CATS; i++) {
            state.cats[i].last_pos.x = cl[i][0];
            state.cats[i].last_pos.y = cl[i][1];
        }
    }

    // cat_direction (옵션)
    if (state_dict.contains("cat_direction")) {
        auto cd = state_dict["cat_direction"].cast<std::vector<int>>();
        for (size_t i = 0; i < cd.size() && i < simulator::Config::NUM_CATS; i++) {
            state.cats[i].direction = cd[i];
        }
    }

    // sc (작은 치즈)
    auto sc = state_dict["sc"].cast<std::vector<std::vector<int>>>();
    for (int i = 0; i < simulator::MAP_SIZE; i++) {
        for (int j = 0; j < simulator::MAP_SIZE; j++) {
            state.sc[i][j] = sc[i][j];
        }
    }

    // wall
    auto wall = state_dict["wall"].cast<std::vector<std::vector<int>>>();
    for (int i = 0; i < simulator::MAP_SIZE; i++) {
        for (int j = 0; j < simulator::MAP_SIZE; j++) {
            state.wall[i][j] = wall[i][j];
        }
    }

    // junc
    auto junc = state_dict["junc"].cast<std::vector<std::vector<int>>>();
    for (int i = 0; i < simulator::MAP_SIZE; i++) {
        for (int j = 0; j < simulator::MAP_SIZE; j++) {
            state.junc[i][j] = junc[i][j];
        }
    }

    // deadend
    auto deadend = state_dict["deadend"].cast<std::vector<std::vector<int>>>();
    for (int i = 0; i < simulator::MAP_SIZE; i++) {
        for (int j = 0; j < simulator::MAP_SIZE; j++) {
            state.deadend[i][j] = deadend[i][j];
        }
    }

    // movbc
    auto movbc = state_dict["movbc"].cast<std::vector<std::vector<int>>>();
    for (size_t i = 0; i < movbc.size() && i < simulator::Config::NUM_MOVBC; i++) {
        state.movbc[i].pos.x = movbc[i][0];
        state.movbc[i].pos.y = movbc[i][1];
        state.movbc[i].last_pos = state.movbc[i].pos;
        state.movbc[i].active = true;
    }

    // crzbc
    auto crzbc = state_dict["crzbc"].cast<std::vector<std::vector<int>>>();
    for (size_t i = 0; i < crzbc.size() && i < simulator::Config::NUM_CRZBC; i++) {
        state.crzbc[i].pos.x = crzbc[i][0];
        state.crzbc[i].pos.y = crzbc[i][1];
        state.crzbc[i].last_pos = state.crzbc[i].pos;
        state.crzbc[i].active = true;
    }

    // crzbc_direction (옵션)
    if (state_dict.contains("crzbc_direction")) {
        auto cd = state_dict["crzbc_direction"].cast<std::vector<int>>();
        for (size_t i = 0; i < cd.size() && i < simulator::Config::NUM_CRZBC; i++) {
            state.crzbc[i].direction = cd[i];
        }
    }

    // 스칼라 값들
    state.score = state_dict["score"].cast<int>();
    state.life = state_dict["life"].cast<int>();
    state.step = state_dict["step"].cast<int>();
    state.step_limit = state_dict.contains("step_limit") ?
        state_dict["step_limit"].cast<int>() : simulator::Config::DEFAULT_STEP_LIMIT;
    state.run = state_dict.contains("run") ?
        state_dict["run"].cast<int>() : 0;
    state.func_chance = state_dict.contains("func_chance") ?
        state_dict["func_chance"].cast<int>() : simulator::Config::DEFAULT_FUNC_CHANCE;
    state.red_zone = state_dict.contains("red_zone") ?
        state_dict["red_zone"].cast<int>() : simulator::Config::DEFAULT_RED_ZONE;

    // 플래그
    state.win_sign = state_dict.contains("win_sign") ?
        state_dict["win_sign"].cast<bool>() : false;
    state.lose_sign = state_dict.contains("lose_sign") ?
        state_dict["lose_sign"].cast<bool>() : false;
    state.catched = state_dict.contains("catched") ?
        state_dict["catched"].cast<bool>() : false;

    return state;
}

// ============================================================
// GameState → Python dict 변환 헬퍼
// ============================================================
py::dict state_to_dict(const simulator::GameState& state) {
    py::dict result;

    // mouse
    result["mouse"] = std::vector<int>{state.mouse.x, state.mouse.y};
    result["mouse_last_pos"] = std::vector<int>{state.mouse_last.x, state.mouse_last.y};

    // cat
    std::vector<std::vector<int>> cat_vec;
    std::vector<std::vector<int>> cat_last_vec;
    std::vector<int> cat_dir_vec;
    for (const auto& c : state.cats) {
        cat_vec.push_back({c.pos.x, c.pos.y});
        cat_last_vec.push_back({c.last_pos.x, c.last_pos.y});
        cat_dir_vec.push_back(c.direction);
    }
    result["cat"] = cat_vec;
    result["cat_last_pos"] = cat_last_vec;
    result["cat_direction"] = cat_dir_vec;

    // 맵 데이터
    std::vector<std::vector<int>> sc_vec(simulator::MAP_SIZE, std::vector<int>(simulator::MAP_SIZE));
    std::vector<std::vector<int>> wall_vec(simulator::MAP_SIZE, std::vector<int>(simulator::MAP_SIZE));
    std::vector<std::vector<int>> junc_vec(simulator::MAP_SIZE, std::vector<int>(simulator::MAP_SIZE));
    std::vector<std::vector<int>> deadend_vec(simulator::MAP_SIZE, std::vector<int>(simulator::MAP_SIZE));

    for (int i = 0; i < simulator::MAP_SIZE; i++) {
        for (int j = 0; j < simulator::MAP_SIZE; j++) {
            sc_vec[i][j] = state.sc[i][j];
            wall_vec[i][j] = state.wall[i][j];
            junc_vec[i][j] = state.junc[i][j];
            deadend_vec[i][j] = state.deadend[i][j];
        }
    }
    result["sc"] = sc_vec;
    result["wall"] = wall_vec;
    result["junc"] = junc_vec;
    result["deadend"] = deadend_vec;

    // movbc
    std::vector<std::vector<int>> movbc_vec;
    for (const auto& bc : state.movbc) {
        movbc_vec.push_back({bc.pos.x, bc.pos.y});
    }
    result["movbc"] = movbc_vec;

    // crzbc
    std::vector<std::vector<int>> crzbc_vec;
    std::vector<int> crzbc_dir_vec;
    for (const auto& bc : state.crzbc) {
        crzbc_vec.push_back({bc.pos.x, bc.pos.y});
        crzbc_dir_vec.push_back(bc.direction);
    }
    result["crzbc"] = crzbc_vec;
    result["crzbc_direction"] = crzbc_dir_vec;

    // 스칼라
    result["score"] = static_cast<int>(state.score);
    result["life"] = static_cast<int>(state.life);
    result["step"] = static_cast<int>(state.step);
    result["step_limit"] = static_cast<int>(state.step_limit);
    result["run"] = static_cast<int>(state.run);
    result["func_chance"] = static_cast<int>(state.func_chance);
    result["red_zone"] = static_cast<int>(state.red_zone);

    // 플래그
    result["win_sign"] = state.win_sign;
    result["lose_sign"] = state.lose_sign;
    result["catched"] = state.catched;

    return result;
}

// ============================================================
// pybind11 모듈 정의
// ============================================================
PYBIND11_MODULE(cpp_simulator, m) {
    m.doc() = "C++ Game Simulator Extension for GRPO Training";

    // GameState 클래스
    py::class_<simulator::GameState>(m, "GameState")
        .def(py::init<>())
        .def("init_level3", &simulator::GameState::init_level3)
        .def("reset", &simulator::GameState::reset)
        .def("count_remaining_cheese", &simulator::GameState::count_remaining_cheese)
        .def_readwrite("score", &simulator::GameState::score)
        .def_readwrite("life", &simulator::GameState::life)
        .def_readwrite("step", &simulator::GameState::step)
        .def_readwrite("win_sign", &simulator::GameState::win_sign)
        .def_readwrite("lose_sign", &simulator::GameState::lose_sign);

    // Simulator 클래스
    py::class_<simulator::Simulator>(m, "Simulator")
        .def(py::init<int>(), py::arg("level") = 3)

        // 핵심 API - GIL 해제로 병렬 실행 가능
        .def("simulate_program", &simulator::Simulator::simulate_program,
             py::arg("program"),
             py::call_guard<py::gil_scoped_release>(),
             "Execute program and return score (does not modify state)")

        .def("simulate_program_and_apply", &simulator::Simulator::simulate_program_and_apply,
             py::arg("program"),
             py::call_guard<py::gil_scoped_release>())

        // 상태 관리 (dict 호환)
        .def("restore_state", [](simulator::Simulator& self, py::dict state_dict) {
            self.restore_state(dict_to_state(state_dict));
        }, py::arg("state_dict"),
           "Restore state from Python dict")

        .def("get_state_dict", [](const simulator::Simulator& self) {
            return state_to_dict(self.get_state());
        }, "Get state as Python dict")

        .def("reset", &simulator::Simulator::reset)

        // 캐시 관리 (전역 공유)
        .def("initialize_cache", &simulator::Simulator::initialize_cache,
             "Pre-compute BFS distance maps for all 121 positions (shared globally)")
        .def_static("enable_global_cache", &simulator::Simulator::enable_global_cache,
             "Enable using the pre-computed global distance cache")
        .def_static("disable_global_cache", &simulator::Simulator::disable_global_cache,
             "Disable using the global distance cache")
        .def_static("is_cache_initialized", &simulator::Simulator::is_cache_initialized,
             "Check if global distance cache is initialized")
        .def_static("is_cache_enabled", &simulator::Simulator::is_cache_enabled,
             "Check if global cache is enabled")

        // 속성
        .def_property_readonly("score", &simulator::Simulator::get_score)
        .def_property_readonly("life", &simulator::Simulator::get_life)
        .def_property_readonly("step", &simulator::Simulator::get_step)
        .def_property_readonly("win_sign", &simulator::Simulator::is_win)
        .def_property_readonly("lose_sign", &simulator::Simulator::is_lose);

    // 배치 시뮬레이션 함수
    // 주의: dict_to_state는 GIL 보유 상태에서 실행, batch_simulate만 GIL 해제
    m.def("batch_simulate", [](const std::vector<std::vector<int>>& programs,
                                py::dict initial_state_dict,
                                int num_threads) {
        // GIL 보유 상태에서 Python dict → C++ 변환
        simulator::GameState initial_state = dict_to_state(initial_state_dict);

        // GIL 해제 후 병렬 시뮬레이션
        std::vector<float> results;
        {
            py::gil_scoped_release release;
            results = simulator::batch_simulate(programs, initial_state, num_threads);
        }
        return results;
    }, py::arg("programs"),
       py::arg("initial_state"),
       py::arg("num_threads") = 0,
       "Batch simulate multiple programs in parallel");

    // 상수 노출
    m.attr("MAP_SIZE") = simulator::MAP_SIZE;
    m.attr("TOKEN_END") = simulator::Token::END;
    m.attr("TOKEN_LOOP") = simulator::Token::LOOP;
    m.attr("TOKEN_IF") = simulator::Token::IF;
}
