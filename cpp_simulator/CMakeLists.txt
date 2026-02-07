cmake_minimum_required(VERSION 3.15)
project(cpp_simulator LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# 최적화 옵션
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -DNDEBUG")

# pybind11 찾기
find_package(pybind11 CONFIG REQUIRED)

# OpenMP (선택적)
find_package(OpenMP)

# 소스 파일
set(SOURCES
    src/simulator.cpp
    src/bindings.cpp
)

# Python 모듈 빌드
pybind11_add_module(cpp_simulator ${SOURCES})

target_include_directories(cpp_simulator PRIVATE include)

# OpenMP 링크 (사용 가능한 경우)
if(OpenMP_CXX_FOUND)
    target_link_libraries(cpp_simulator PRIVATE OpenMP::OpenMP_CXX)
    target_compile_definitions(cpp_simulator PRIVATE USE_OPENMP)
    message(STATUS "OpenMP found and enabled")
else()
    message(STATUS "OpenMP not found, building without parallel support")
endif()

# 설치
install(TARGETS cpp_simulator DESTINATION .)
