CXX ?= c++
CXXFLAGS ?= -O3 -march=native
CXXFLAGS += -std=c++17 -Wall -Wextra -pthread
SRCS = src/rule.cpp src/search.cpp src/options.cpp src/classic.cpp src/report.cpp src/main.cpp
OBJS = $(SRCS:src/%.cpp=build/%.o)

drift: $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $(OBJS)

build/%.o: src/%.cpp src/*.h | build
	$(CXX) $(CXXFLAGS) -c -o $@ $<

build:
	mkdir -p build

tests/ruletest: tests/ruletest.cpp src/rule.cpp src/rule.h
	$(CXX) $(CXXFLAGS) -Isrc -o $@ tests/ruletest.cpp src/rule.cpp

test: drift tests/ruletest
	tests/ruletest
	python3 tests/regress.py --seconds 5

clean:
	rm -rf build drift tests/ruletest

.PHONY: test clean
