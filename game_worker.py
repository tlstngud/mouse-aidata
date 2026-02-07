#!/usr/bin/env python3
"""
Game parallel worker (no torch, CPU only)
Used with multiprocessing spawn mode
"""

import os
import sys
import random

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# pygame headless
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'


def get_effective_length(program):
    """Calculate effective length of a program"""
    LOOP_TOKEN = 110
    END_TOKEN = 112
    effective_len = 0.0
    i = 0
    while i < len(program):
        token = program[i]
        if token == END_TOKEN:
            break
        elif token == LOOP_TOKEN:
            effective_len += 1.5
            i += 3
        else:
            effective_len += 1.0
            i += 1
    return effective_len


def get_state_vector_list(sim):
    """Extract state vector from simulator (828 dims, returns list - no torch needed)"""
    state_dict = sim.get_state_dict()
    state = []
    DYNAMIC_SCALE = 10.0

    for grid_name in ['wall', 'sc', 'junc', 'deadend']:
        grid = state_dict[grid_name]
        for row in grid:
            if grid_name == 'sc':
                state.extend([v * DYNAMIC_SCALE for v in row])
            else:
                state.extend(row)

    mouse = state_dict['mouse']
    state.extend([float(mouse[0]), float(mouse[1])])

    cat_list = state_dict.get('cat', [])
    for i in range(6):
        if i < len(cat_list):
            state.extend([float(cat_list[i][0]), float(cat_list[i][1])])
        else:
            state.extend([-1.0, -1.0])

    bc_list = state_dict.get('crzbc', [])
    for i in range(5):
        if i < len(bc_list):
            state.extend([float(bc_list[i][0]), float(bc_list[i][1])])
        else:
            state.extend([-1.0, -1.0])

    while len(state) < 484 + 65:
        state.append(0.0)

    state.append(state_dict.get('score', 0) / 1000.0 * DYNAMIC_SCALE)
    state.append(state_dict.get('life', 3) * DYNAMIC_SCALE / 3.0)
    state.append(state_dict.get('run', 0) * DYNAMIC_SCALE / 20.0)
    state.append(DYNAMIC_SCALE if state_dict.get('win_sign', False) else 0.0)
    state.append(DYNAMIC_SCALE if state_dict.get('lose_sign', False) else 0.0)
    step = state_dict.get('step', 0)
    step_limit = state_dict.get('step_limit', 200)
    state.append(step / step_limit * DYNAMIC_SCALE if step_limit > 0 else 0.0)

    while len(state) < 828:
        state.append(0.0)

    return state[:828]


def generate_running_max_standalone(n_programs, game_state_dict, cpp_threads):
    """Generate Running Max programs (standalone)"""
    from cpp_simulator_adapter import LightweightGameSimulator
    import cpp_simulator as cpp_sim

    END_TOKEN = 112
    LOOP_TOKEN = 110
    MAX_TOKENS = 10
    STRUCTURE_BAN_THRESHOLD = 8

    running_max_programs = []

    for prog_idx in range(n_programs):
        program = []
        sim = LightweightGameSimulator(level=game_state_dict.get('level', 3))
        sim.restore_state(game_state_dict)

        while len(program) < MAX_TOKENS:
            current_len = len(program)
            allow_structure = current_len < STRUCTURE_BAN_THRESHOLD

            cached_state = sim.get_state_dict()
            initial_score = sim.score

            candidates_to_eval = []

            for dir_token in [0, 1, 2, 3]:
                candidates_to_eval.append(([dir_token], 1.0, True))

            if allow_structure:
                for _ in range(96):
                    num_token = random.choice([104, 105, 106, 107, 108, 109, 100])
                    dir_token = random.choice([0, 1, 2, 3])
                    candidates_to_eval.append(([LOOP_TOKEN, num_token, dir_token], 0.5, False))

            progs_to_sim = [program + cand[0] for cand in candidates_to_eval]
            scores = cpp_sim.batch_simulate(progs_to_sim, cached_state, cpp_threads)

            all_candidates = []
            for i, (tokens, mult, is_dir) in enumerate(candidates_to_eval):
                score = (scores[i] - initial_score) * mult
                if is_dir:
                    score += 15.0
                all_candidates.append((score, tokens))

            if all_candidates:
                max_score = max(c[0] for c in all_candidates)
                best_candidates = [c[1] for c in all_candidates if c[0] == max_score]
                best_tokens = random.choice(best_candidates)
            else:
                best_tokens = [END_TOKEN]

            program.extend(best_tokens)

            sim.restore_state(cached_state)
            if best_tokens[0] != END_TOKEN:
                sim.simulate_program_and_apply(best_tokens)

            if best_tokens[-1] == END_TOKEN:
                break

        if not program or program[-1] != END_TOKEN:
            program.append(END_TOKEN)

        running_max_programs.append(program)

    return running_max_programs


def evaluate_programs_standalone(programs, game_state_dict, cpp_threads):
    """Evaluate programs (standalone) - returns total_score"""
    import cpp_simulator as cpp_sim
    from reward_config import RewardConfig, compute_structure_reward

    reward_cfg = RewardConfig()
    initial_score = game_state_dict.get('score', 0)
    END_TOKEN = 112
    LOOP_TOKEN = 110

    all_prefixes = []
    prefix_metadata = []

    for prog_idx, prog in enumerate(programs):
        i = 0
        while i < len(prog):
            token = prog[i]
            if token == END_TOKEN:
                prefix_metadata.append((prog_idx, i, 1, True))
                i += 1
            elif token == LOOP_TOKEN and i + 2 < len(prog):
                all_prefixes.append(prog[:i+3])
                prefix_metadata.append((prog_idx, i, 3, False))
                i += 3
            else:
                all_prefixes.append(prog[:i+1])
                prefix_metadata.append((prog_idx, i, 1, False))
                i += 1

    if all_prefixes:
        all_scores = cpp_sim.batch_simulate(all_prefixes, game_state_dict, cpp_threads)
    else:
        all_scores = []

    prog_final_scores = {i: initial_score for i in range(len(programs))}
    prog_prev_scores = {i: initial_score for i in range(len(programs))}

    score_idx = 0
    for prog_idx, start_idx, num_tokens, is_end in prefix_metadata:
        if not is_end:
            if score_idx < len(all_scores):
                prog_prev_scores[prog_idx] = all_scores[score_idx]
                prog_final_scores[prog_idx] = all_scores[score_idx]
                score_idx += 1

    results = []
    for prog_idx, prog in enumerate(programs):
        final_score = prog_final_scores[prog_idx]
        game_delta = final_score - initial_score
        structure_reward = compute_structure_reward(prog, reward_cfg)

        if game_delta > 0:
            scaled_delta = game_delta * reward_cfg.cheese_reward_scale
        elif game_delta <= -450:
            scaled_delta = game_delta * reward_cfg.cat_penalty_scale
        else:
            scaled_delta = game_delta * reward_cfg.wall_penalty_scale

        total_score = scaled_delta + structure_reward

        results.append({
            'prog_idx': prog_idx,
            'program': prog,
            'total_score': total_score,
            'game_delta': game_delta,
        })

    return results


def game_worker(worker_args):
    """Multiprocessing worker: run a single complete game (CPU only, no torch)"""
    game_idx, level, max_runs, cpp_threads, top_k_sft = worker_args

    from cpp_simulator_adapter import LightweightGameSimulator

    game = LightweightGameSimulator(level=level)
    game.reset()

    runs_data = []

    for run in range(max_runs):
        if game.win_sign or game.lose_sign:
            break

        state_vec = get_state_vector_list(game)
        game_state_dict = game.get_state_dict()

        programs = generate_running_max_standalone(32, game_state_dict, cpp_threads)
        eval_results = evaluate_programs_standalone(programs, game_state_dict, cpp_threads)

        best_idx = max(range(len(eval_results)),
                      key=lambda i: (eval_results[i]['total_score'],
                                    -get_effective_length(programs[i])))
        best_program = programs[best_idx]

        prog_to_execute = [t for t in best_program if t != 112]
        try:
            game.execute_program(prog_to_execute)
        except Exception:
            pass

        sorted_idx = sorted(range(len(eval_results)),
                           key=lambda i: eval_results[i]['total_score'],
                           reverse=True)[:top_k_sft]
        top_programs = [programs[i] for i in sorted_idx]
        top_scores = [eval_results[i]['total_score'] for i in sorted_idx]

        runs_data.append({
            'state_vec': state_vec,
            'programs': top_programs,
            'scores': top_scores,
        })

    sc_left = sum(sum(1 for v in row if v == 1) for row in game.sc)
    bc_left = 0
    if hasattr(game, 'movbc'):
        bc_left += sum(1 for p in game.movbc if p != [-1, -1])
    if hasattr(game, 'crzbc'):
        bc_left += sum(1 for p in game.crzbc if p != [-1, -1])

    return {
        'runs_data': runs_data,
        'final_score': game.score,
        'win': game.win_sign,
        'sc_left': sc_left,
        'bc_collected': 4 - bc_left,
        'life': getattr(game, 'life', 3),
        'n_runs': len(runs_data),
    }
