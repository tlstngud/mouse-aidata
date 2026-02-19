# Mouse AI Game - SFT Data Generation

CPU-only data generation pipeline for the Mouse AI game. Generates SFT (Supervised Fine-Tuning) training data by running parallel game simulations with a Running Max search algorithm.

## Overview

This tool generates training data for a transformer model that learns to play a mouse-and-cheese game. Each game consists of up to 20 runs where the mouse navigates an 11x11 grid to collect cheese while avoiding cats.

**For each game run, the pipeline:**
1. Captures the current game state as an 828-dimensional vector
2. Generates 32 candidate programs using Running Max search (greedy token-by-token construction with C++ batch simulation)
3. Evaluates all programs and selects the top-K by total reward score
4. Executes the best program to advance the game state
5. Saves (state_vector, top-K programs, scores) as an SFT training sample

## Prerequisites

- **Python 3.10+** (tested with 3.12)
- **PyTorch** (for saving data files)
- **C++ compiler** with C++17 support (g++ or clang++)
- **pybind11** (`pip install pybind11`)
- **OpenMP** (optional, for parallel batch simulation)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/tlstngud/mouse-aidata.git
cd mouse-aidata
```

### 2. Build the C++ simulator

```bash
cd cpp_simulator
pip install -e .
cd ..
```

This compiles the C++ game simulator as a Python extension module (`cpp_simulator`). The build automatically detects and enables OpenMP if available.

### 3. Verify the build

```python
python -c "import cpp_simulator; print('C++ simulator loaded successfully')"
```

If the C++ module is not available, the system will automatically fall back to the pure Python simulator (significantly slower).

## Usage

### Basic usage (default: 10,000 games, 20 parallel workers)

```bash
CUDA_VISIBLE_DEVICES="" python generate_sft_data.py
```

### Custom parameters

```bash
CUDA_VISIBLE_DEVICES="" python generate_sft_data.py \
    --n_games 10000 \
    --n_parallel 20 \
    --group_size 32 \
    --top_k 1 \
    --cpp_threads 3 \
    --save_every 1000 \
    --output_dir ./sft_data
```

### Command-line arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--n_games` | 10000 | Total number of games to simulate |
| `--n_parallel` | 20 | Number of parallel game workers |
| `--group_size` | 32 | Running Max group size (candidates per run) |
| `--top_k` | 1 | Number of top programs to keep per run |
| `--cpp_threads` | 3 | C++ OpenMP threads per game (for batch_simulate) |
| `--level` | 3 | Game level (only level 3 is currently supported) |
| `--max_runs` | 20 | Maximum runs per game |
| `--save_every` | 1000 | Save checkpoint every N games |
| `--output_dir` | sft_data | Output directory for generated data |

### Recommended settings by machine

| Machine | n_parallel | cpp_threads | Notes |
|---------|-----------|-------------|-------|
| 4-core laptop | 4 | 1 | Conservative, ~2 games/min |
| 8-core desktop | 8 | 2 | Balanced, ~5 games/min |
| 16-core server | 16 | 2 | Good throughput, ~12 games/min |
| 32-core server | 30 | 2 | High throughput, ~20 games/min |

**Tip:** Set `n_parallel * cpp_threads` to roughly match your total CPU thread count.

## Output Format

Data is saved as `.pt` (PyTorch) files:

```
sft_data/
├── sft_data_g1000.pt    # Checkpoint at 1000 games
├── sft_data_g2000.pt    # Checkpoint at 2000 games
├── ...
└── sft_data_final.pt    # Final result
```

Each `.pt` file contains:

```python
import torch
data = torch.load('sft_data/sft_data_final.pt')

print(data['n_games'])    # Total games played
print(data['wins'])       # Total wins
print(data['win_rate'])   # Win rate
print(data['n_runs'])     # Total runs across all games

# Training samples
for sample in data['data']:
    state_vec = sample['state_vec']    # 828-dim game state (list[float])
    programs = sample['programs']       # Top-K programs (list[list[int]])
    scores = sample['scores']           # Corresponding reward scores (list[float])
```

### Token vocabulary

| Token | Meaning |
|-------|---------|
| 0 | UP |
| 1 | DOWN |
| 2 | LEFT |
| 3 | RIGHT |
| 100 | Number 10 (loop repeat) |
| 104-109 | Numbers 4-9 (loop repeat) |
| 110 | LOOP (followed by NUM + DIR) |
| 112 | END |

## Project Structure

```
mouse-aidata/
├── README.md
├── generate_sft_data.py       # Main data generation script
├── game_worker.py             # Parallel game worker (no torch)
├── reward_config.py           # Reward calculation config
├── cpp_simulator_adapter.py   # C++/Python simulator adapter
├── lightweight_simulator.py   # Python fallback simulator
├── function_library.py        # Function library for program parsing
└── cpp_simulator/
    ├── setup.py               # Build script (pip install -e .)
    ├── pyproject.toml          # Build system config
    ├── CMakeLists.txt          # Alternative CMake build
    ├── include/
    │   ├── constants.hpp       # Game constants and token definitions
    │   ├── game_state.hpp      # Game state structure
    │   ├── simulator.hpp       # Simulator class declaration
    │   └── function_library.hpp # C++ function library
    └── src/
        ├── simulator.cpp       # Simulator implementation
        └── bindings.cpp        # pybind11 Python bindings
```

## Game Description

The mouse navigates an 11x11 grid maze (Level 3):
- **75 small cheese** (10 points each)
- **4 big cheese** (500 points each)
- **2 cats** (avoid them! -500 points on collision, random movement at junctions)
- **20 runs maximum** per game
- Each run executes a program (sequence of movement commands)
- Win condition: collect all cheese

## Notes

- The C++ simulator is ~13x faster than the Python fallback
- GPU is NOT needed for data generation -- set `CUDA_VISIBLE_DEVICES=""`
- PyTorch is only used for saving data files (`torch.save`)
- Data generation is embarrassingly parallel; scale `n_parallel` to your CPU core count
- Memory usage is roughly 100-200 MB per worker process
