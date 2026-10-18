// Everything a run is configured with, filled either from dr2.c's command
// language (classic.cpp) or from named options / a config file (options.cpp).
#pragma once
#include <iosfwd>
#include <string>
#include <vector>

#include "rule.h"
#include "search.h"

namespace drift {

struct Options {
  Params params;
  Rule rule;
  bool ruleSet = false;
  bool classic = false;

  // Which outcomes to print
  bool skipStable = false, skipFizzle = false, skipMaxgen = false, skipPeriodic = false;
  bool skipKnown = false;          // only print oscillators/fizzles not in known rotors
  int minPeriod = 0;
  bool mustReach = false;          // results must change a --must-reach cell
  long maxResults = 10000;         // stop printing after this many (0 = no limit)
  int perRotor = 10;               // modern mode default; classic prints everything                // print at most this many results per rotor (0 = all)
  bool noPics = false, noRle = false, showFin = false, showAll = false;

  std::string knownRotorsFile;     // empty = default lookup
  bool knownRotorsExplicit = false;
  std::string jsonl;               // append one JSON object per result
  std::string checkpoint;          // write resumable state here
  double checkpointEvery = 300;
  double progressEvery = 10;
  bool quiet = false;
  bool dryRun = false;
  bool showRule = false;
  int threads = 0;                 // 0 = all cores (modern), 1 (classic)
  long long maxSteps = 0;          // stop after this many search steps (0 = no limit)
  std::string resume;              // checkpoint to resume from

  // Pattern placement (modern mode): pattern-relative coordinates are
  // shifted by (top, left) once the pattern has been placed.
  int top = 0, left = 0, patHeight = 0, patWidth = 0;
  std::vector<std::string> warnings;
};

// dr2.c's command language. Prints dr2.c's messages to stdout.
void readClassic(const std::vector<std::string> &args, std::istream &in, Options &o);

// Named options and config files. Throws std::runtime_error with a message
// meant for the user. Returns false if the program should exit (e.g. --help).
bool readModern(const std::vector<std::string> &args, Options &o);
void printHelp();

// Pattern files: dr2.c's character grid or a LifeHistory RLE. Returns dr2.c
// characters, one string per row, the last row ending in '!'.
std::vector<std::string> loadPatternText(const std::string &text);

}  // namespace drift
