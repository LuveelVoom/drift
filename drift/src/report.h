// Printing of results: dr2.c's exact format (classic mode) or drift's own
// format with numbered results, pattern-relative coordinates, RLE and JSON.
// All calls must be serialized by the caller.
#pragma once
#include <cstdint>
#include <cstdio>
#include <string>
#include <unordered_set>

#include "options.h"
#include "search.h"

namespace drift {

class Reporter {
 public:
  Reporter(const Options &o, const KnownRotors *k, size_t nknown);
  ~Reporter();

  bool hashnew(uint64_t h) { return hashes.insert(h).second; }
  void forget(uint64_t h) { hashes.erase(h); }
  void outcome(Search &s, Outcome o, int per, bool semifzl, uint64_t h);
  void newMaxGen(Search &s);
  void tick(Search &s);
  void note(Search &s, const std::string &msg);

  void header(const Search &base, int threads);
  void footer(double seconds, long long steps, bool finished, bool resumed);

  // State that survives a checkpoint
  std::unordered_set<uint64_t> hashes;
  long counts[4] = {0, 0, 0, 0};   // all outcomes found, by Outcome
  long printed = 0, unknownOsc = 0;
  int maxgen = 0;                  // highest generation reached so far

 private:
  const Options &o;
  size_t nknown;
  FILE *json = nullptr;

  void classic(Search &s, Outcome o, int per, bool semifzl, uint64_t h);
  void modern(Search &s, Outcome o, int per, bool semifzl);
  std::string picture(const Search &s, int g, std::string *lifehistory, std::string *plain) const;
};

}  // namespace drift
