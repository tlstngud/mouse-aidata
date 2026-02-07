#!/usr/bin/env python3
"""
SFT Data Generation Script (CPU only)
- N_PARALLEL games in parallel
- Each game: 32 Running Max -> top-16 programs + state vectors
- Save every 1000 games
"""
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import argparse
import time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from collections import deque

# game_worker does not import torch
from game_worker import game_worker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--n_games', type=int, default=10000, help='Total number of games')
    parser.add_argument('--n_parallel', type=int, default=30, help='Number of parallel games')
    parser.add_argument('--cpp_threads', type=int, default=2, help='C++ threads per game')
    parser.add_argument('--level', type=int, default=3)
    parser.add_argument('--max_runs', type=int, default=20)
    parser.add_argument('--top_k_sft', type=int, default=16)
    parser.add_argument('--save_every', type=int, default=1000, help='Save interval (games)')
    parser.add_argument('--output_dir', type=str, default='./sft_data')
    parser.add_argument('--resume_from', type=int, default=0, help='Resume from game number')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print('=' * 70)
    print('SFT Data Generation')
    print(f'  Total games: {args.n_games}')
    print(f'  Parallel: {args.n_parallel}')
    print(f'  C++ threads/game: {args.cpp_threads}')
    print(f'  Running Max: 32 -> top-{args.top_k_sft}')
    print(f'  Output dir: {args.output_dir}')
    print('=' * 70)

    # Worker pool (spawn mode)
    spawn_ctx = multiprocessing.get_context('spawn')
    pool = ProcessPoolExecutor(max_workers=args.n_parallel, mp_context=spawn_ctx)

    all_samples = []  # Current chunk samples
    total_samples = 0
    total_wins = 0
    game_idx = args.resume_from
    chunk_start_game = game_idx
    recent_scores = deque(maxlen=100)

    start_time = time.time()

    try:
        while game_idx < args.n_games:
            batch_start = time.time()
            batch_size = min(args.n_parallel, args.n_games - game_idx)

            worker_args = [
                (i, args.level, args.max_runs, args.cpp_threads, args.top_k_sft)
                for i in range(batch_size)
            ]

            game_results = list(pool.map(game_worker, worker_args))

            # Collect samples
            batch_samples = 0
            batch_wins = 0
            for result in game_results:
                for run_data in result['runs_data']:
                    all_samples.append({
                        'state_vec': run_data['state_vec'],    # list[828]
                        'programs': run_data['programs'],       # list of 16 programs
                        'scores': run_data['scores'],           # list of 16 scores
                    })
                    batch_samples += 1
                    total_samples += 1

                if result['win']:
                    batch_wins += 1
                    total_wins += 1
                recent_scores.append(result['final_score'])

            game_idx += batch_size
            elapsed = time.time() - start_time
            eps_per_min = game_idx / (elapsed / 60) if elapsed > 0 else 0
            batch_time = time.time() - batch_start
            avg_score = sum(recent_scores) / len(recent_scores) if recent_scores else 0

            print(f'Game {game_idx:5d}/{args.n_games} | '
                  f'{batch_time:.0f}s | {eps_per_min:.1f} eps/min | '
                  f'Wins: {batch_wins}/{batch_size} ({total_wins}/{game_idx} = {total_wins/game_idx*100:.1f}%) | '
                  f'Samples: {batch_samples} (total: {total_samples}) | '
                  f'Avg: {avg_score:.0f}')

            # Periodic save
            if game_idx % args.save_every == 0 or game_idx >= args.n_games:
                import pickle
                chunk_path = os.path.join(
                    args.output_dir,
                    f'sft_chunk_{chunk_start_game:05d}_{game_idx:05d}.pkl'
                )
                with open(chunk_path, 'wb') as f:
                    pickle.dump(all_samples, f)
                print(f'  -> Saved: {chunk_path} ({len(all_samples)} samples)')

                all_samples = []
                chunk_start_game = game_idx

    finally:
        pool.shutdown(wait=False)

        # Save remaining samples
        if all_samples:
            import pickle
            chunk_path = os.path.join(
                args.output_dir,
                f'sft_chunk_{chunk_start_game:05d}_{game_idx:05d}.pkl'
            )
            with open(chunk_path, 'wb') as f:
                pickle.dump(all_samples, f)
            print(f'  -> Saved: {chunk_path} ({len(all_samples)} samples)')

    elapsed = time.time() - start_time
    print('\n' + '=' * 70)
    print(f'Data generation complete!')
    print(f'  Total games: {game_idx}')
    print(f'  Total samples: {total_samples}')
    print(f'  Win rate: {total_wins}/{game_idx} ({total_wins/max(game_idx,1)*100:.1f}%)')
    print(f'  Elapsed: {elapsed/3600:.1f} hours')
    print(f'  Output: {args.output_dir}')
    print('=' * 70)


if __name__ == '__main__':
    main()
