cmake_minimum_required(VERSION 3.16)

project(test)

set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)

find_library(MC_SDK_LIB mc_sdk_${CMAKE_HOST_SYSTEM_PROCESSOR}
    PATHS 
        ${CMAKE_SOURCE_DIR}/../../lib
    REQUIRED
)


add_executable(highlevel_demo highlevel_demo.cpp)
target_link_libraries(highlevel_demo ${MC_SDK_LIB})
target_include_directories(highlevel_demo PRIVATE ${CMAKE_SOURCE_DIR}/../../include)

add_executable(lowlevel_demo lowlevel_demo.cpp)
target_link_libraries(lowlevel_demo ${MC_SDK_LIB})
target_include_directories(lowlevel_demo PRIVATE ${CMAKE_SOURCE_DIR}/../../include)
