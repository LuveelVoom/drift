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

# the reference for tests/regress.py: dr2.c with its 64-bit fix, and dr2's knownrotors list
../ref/dr2fixed: ../ref/dr2fixed.c
	cc -O2 -w -std=gnu89 -include stdlib.h -include string.h -include ctype.h -o $@ $<

../ref/knownrotors: ../dr2.zip
	cd ../ref && unzip -o -q ../dr2.zip knownrotors && touch knownrotors

test: drift tests/ruletest ../ref/dr2fixed ../ref/knownrotors
	tests/ruletest
	python3 tests/regress.py --seconds 5

clean:
	rm -rf build drift tests/ruletest

.PHONY: test clean
