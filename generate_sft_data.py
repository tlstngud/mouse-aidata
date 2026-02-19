#!/usr/bin/env python3
"""
오프라인 SFT 데이터 생성 (Running Max 32, 새 시뮬레이터)

1단계: N게임 병렬 실행, 게임당 최대 20런
2단계: 각 런에서 top-K 프로그램 저장
3단계: .pt 파일로 저장 (에폭 학습에 사용)

사용법:
    CUDA_VISIBLE_DEVICES="" python3 generate_sft_data.py \
        --n_games 10000 --n_parallel 20 --group_size 32 --top_k 1 --cpp_threads 3
"""

import os
import sys
import time
import random
import argparse
import torch
import json
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

from game_worker import game_worker, get_state_vector_list


def main():
    parser = argparse.ArgumentParser(description='Generate SFT data offline')
    parser.add_argument('--n_games', type=int, default=10000, help='Total games to generate')
    parser.add_argument('--n_parallel', type=int, default=20, help='Parallel games per batch')
    parser.add_argument('--group_size', type=int, default=32, help='Running Max group size')
    parser.add_argument('--top_k', type=int, default=1, help='Top-K programs per run')
    parser.add_argument('--cpp_threads', type=int, default=3, help='C++ threads per game')
    parser.add_argument('--level', type=int, default=3, help='Game level')
    parser.add_argument('--max_runs', type=int, default=20, help='Max runs per game')
    parser.add_argument('--output_dir', type=str, default='sft_data', help='Output directory')
    parser.add_argument('--save_every', type=int, default=1000, help='Save checkpoint every N games')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("=" * 70)
    print(f"오프라인 SFT 데이터 생성")
    print(f"시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"설정: {args.n_games}게임, {args.n_parallel}개 병렬, RM{args.group_size}, top-{args.top_k}")
    print(f"cpp_threads/game: {args.cpp_threads} (total: {args.n_parallel * args.cpp_threads})")
    print(f"저장: {args.output_dir}")
    print("=" * 70)

    all_data = []  # (state_vec, programs, scores) 리스트
    total_wins = 0
    total_games = 0
    total_runs = 0
    total_score = 0

    start_time = time.time()
    game_idx = 0

    while game_idx < args.n_games:
        batch_size = min(args.n_parallel, args.n_games - game_idx)

        worker_args = [
            (i, args.level, args.max_runs, args.cpp_threads, args.top_k, args.group_size)
            for i in range(batch_size)
        ]

        batch_start = time.time()

        with ProcessPoolExecutor(max_workers=batch_size) as executor:
            results = list(executor.map(game_worker, worker_args))

        batch_time = time.time() - batch_start

        # 결과 수집
        batch_wins = 0
        batch_score = 0
        for r in results:
            total_games += 1
            total_score += r['final_score']
            batch_score += r['final_score']
            if r['win']:
                total_wins += 1
                batch_wins += 1

            for run_data in r['runs_data']:
                all_data.append({
                    'state_vec': run_data['state_vec'],
                    'programs': run_data['programs'],
                    'scores': run_data['scores'],
                })
                total_runs += 1

        game_idx += batch_size
        elapsed = time.time() - start_time
        eps_min = game_idx / elapsed * 60 if elapsed > 0 else 0

        print(f"Batch {game_idx//batch_size:4d} | Game {game_idx:5d}/{args.n_games} | "
              f"Time: {batch_time:.1f}s | {eps_min:.1f} eps/min | "
              f"Wins: {batch_wins}/{batch_size} | "
              f"Total: {total_wins}/{total_games} ({total_wins/total_games*100:.1f}%) | "
              f"Runs: {total_runs} | "
              f"Avg: {batch_score//batch_size}")

        # 중간 저장
        if game_idx % args.save_every == 0 and game_idx > 0:
            save_path = os.path.join(args.output_dir, f'sft_data_g{game_idx}.pt')
            torch.save({
                'data': all_data,
                'n_games': total_games,
                'n_runs': total_runs,
                'wins': total_wins,
                'win_rate': total_wins / total_games if total_games > 0 else 0,
                'args': vars(args),
            }, save_path)
            print(f"  → 중간 저장: {save_path} ({len(all_data)} 샘플)")

    # 최종 저장
    elapsed = time.time() - start_time
    save_path = os.path.join(args.output_dir, f'sft_data_final.pt')
    torch.save({
        'data': all_data,
        'n_games': total_games,
        'n_runs': total_runs,
        'wins': total_wins,
        'win_rate': total_wins / total_games if total_games > 0 else 0,
        'avg_score': total_score / total_games if total_games > 0 else 0,
        'args': vars(args),
    }, save_path)

    print("\n" + "=" * 70)
    print(f"완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"총 시간: {elapsed/60:.1f}분")
    print(f"게임: {total_games}, 승률: {total_wins}/{total_games} ({total_wins/total_games*100:.1f}%)")
    print(f"총 런 수: {total_runs} (평균 {total_runs/total_games:.1f}런/게임)")
    print(f"총 샘플: {len(all_data)}")
    print(f"저장: {save_path}")
    print("=" * 70)


if __name__ == '__main__':
    main()
