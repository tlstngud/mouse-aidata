from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext
import os

# OpenMP 플래그 설정
extra_compile_args = ["-O3", "-march=native", "-std=c++17"]
extra_link_args = []

# OpenMP 지원 확인
try:
    import subprocess
    result = subprocess.run(["g++", "-fopenmp", "-E", "-"],
                          input=b"", capture_output=True)
    if result.returncode == 0:
        extra_compile_args.append("-fopenmp")
        extra_compile_args.append("-DUSE_OPENMP")
        extra_link_args.append("-fopenmp")
        print("OpenMP support enabled")
except:
    print("OpenMP not available, building without parallel support")

ext_modules = [
    Pybind11Extension(
        "cpp_simulator",
        sources=[
            "src/simulator.cpp",
            "src/bindings.cpp",
        ],
        include_dirs=["include"],
        extra_compile_args=extra_compile_args,
        extra_link_args=extra_link_args,
        language="c++",
    ),
]

setup(
    name="cpp_simulator",
    version="1.0.0",
    author="HardAI",
    description="C++ Game Simulator Extension for GRPO Training",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    python_requires=">=3.8",
)
