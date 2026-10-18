// The drifter search: a port of Dean Hickerson's dr2.c search core.
//
// Two patterns are tracked: a stable background (bkgd) and the current
// generation (curr), which differs from it in a small "changed" region. Both
// start mostly unknown. The search computes generation after generation,
// choosing values for unknown background cells when needed and keeping the
// background stable, and backtracks when the changed region gets too big.
//
// The search order, random choices and pruning are identical to dr2.c, so a
// single-threaded run with the same seed reports the same outcomes in the same
// order. Every free choice is recorded as a "decision" in the setting list so a
// subtree can be described by its decision path (a list of 0/1 values) and
// handed to another thread or written to a checkpoint.
#pragma once
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

#include "rule.h"

namespace drift {

enum { DONTCHANGE = 1, DONTCOUNT = 2, DONTCHECK = 4 };
constexpr int NUMVARS = 200;

struct Region {
  char type = 'r';   // r = rectangle, l = line, p = point, t = triangle
  int minrow = 0, mincol = 0, maxrow = 0, maxcol = 0;
  int r0 = 0, c0 = 0, r1 = 0, c1 = 0, r2 = 0, c2 = 0;
  long orient = 0;
  bool contains(int r, int c) const;
  void shift(int dr, int dc);
};
// Parses "r r0 c0 r1 c1", "l ...", "p r c", "t r0 c0 r1 c1 r2 c2" (the letter
// may be omitted, in which case def is used). Bounds are not clamped here.
bool parseRegion(const std::string &s, Region &reg, char def, std::string &err);

struct PatternOp {
  enum Kind { READ, CLEAR, SETFLAG, CLEARFLAG } kind = READ;
  int r = 0, c = 0;                 // READ: row/col of the top-left character
  std::vector<std::string> lines;   // READ: dr's characters (o . 0 1 , ? : O s 2 3 4)
  Region reg;                       // CLEAR, SETFLAG, CLEARFLAG
  int bit = 0;                      // SETFLAG, CLEARFLAG
};

struct Params {
  int HT = 81, WD = 81, maxgen = 500;
  int maxchng = 9, maxwidth = 3, maxheight = 3, prob = 50;
  unsigned long seed = 1;
  int symm = NOSYMM;
  long var[NUMVARS] = {};
  std::vector<int> reqchgcount;     // dr's "cc" command
  std::vector<PatternOp> ops;
};

struct KnownRotors {
  std::unordered_map<std::string, int> index;   // descriptor -> first entry
  std::vector<std::string> names;
  bool load(const std::string &path, std::string &err);
};

struct OscInfo {
  std::string desc;   // minimal rotor descriptor
  bool known = false;
  std::string name;   // if known
  int gap = 0;        // >0 if the rotor is split: gap between its pieces
  std::string line;   // dr2.c's printed line, including the newline
};

enum Outcome { PERIODIC, STABLE, FIZZLE, MAXGEN };

class Search;
struct Sink {
  virtual ~Sink() {}
  virtual bool hashnew(uint64_t h) = 0;   // false if h was seen before
  virtual void forget(uint64_t h) = 0;
  virtual void outcome(Search &s, Outcome o, int per, bool semifzl, uint64_t h) = 0;
  virtual void newMaxGen(Search &) {}
  virtual void tick(Search &) {}          // every 10^6 search steps (dr2's progress)
  virtual void note(Search &, const std::string &) {}   // dr2's rejection messages
  // Called every 1024 steps at a point where the search may be paused,
  // checkpointed or asked to donate work. Return true to stop the search.
  virtual bool poll(Search &) { return false; }
};

class Search {
 public:
  struct Pt { int r, c; };
  struct Setting {
    int r, c;
    uint8_t val;
    bool free, decision, donated;
    int gen, nay, chg;
  };

  const Rule *rule = nullptr;
  const KnownRotors *known = nullptr;
  Params P;
  int HT = 0, WD = 0;

  // Grid storage has a 2-cell OFF margin around the HT x WD space.
  std::vector<uint8_t> bkgd, curr, flag;
  std::vector<uint16_t> code;   // base-3 code of the 3x3 bkgd window

  std::vector<Pt> chglist;
  std::vector<int> chgd, nays;  // indices into chglist, per generation
  std::vector<int> chgcount, agesm, width, height;
  std::vector<Pt> ulist;        // DONTCHECK cells read from the pattern

  std::vector<Setting> st;
  int nxstng = 0, nwstng = 0;

  int gen = 0, nay = 0, chg = 0;
  bool found = false, semifzl = false;
  int maxgenreached = 0;
  uint64_t rng = 1;
  long long steps = 0;          // computecellorbackup calls
  long countlo = 0, counthi = 0;

  // Decision path this search was started from (see header comment).
  std::vector<uint8_t> prefix;
  size_t replayPos = 0;
  double weight = 1.0;          // share of the whole search tree
  double donatedWeight = 0.0;

  void init(const Params &p, const Rule *r, const KnownRotors *k);  // throws
  void start();                 // dr2's setup between reading input and searching
  bool run(Sink &sink);         // true = subtree finished, false = stopped by poll

  // Work splitting
  bool donate(std::vector<uint8_t> &path, double &w);
  void pending(std::vector<std::pair<std::vector<uint8_t>, double>> &out) const;
  double progress() const;      // explored share of the tree (within weight)
  void seed(uint64_t s) { rng = s; }

  // Reporting helpers (same text as dr2.c)
  std::string display(int g) const;
  std::string dispchgcts(int g) const;
  OscInfo oscinfo(int p, char prefixch);
  uint64_t hash() const;
  int numchanged(int g) const { return nays[g] - chgd[g]; }
  int idx(int r, int c) const { return (r + 2) * S + (c + 2); }
  int stride() const { return S; }

 private:
  int S = 0;
  int OFFS[9];
  std::vector<uint32_t> stamp;
  uint32_t stampv = 0;
  std::vector<uint8_t> cell;    // scratch for rotor descriptors
  std::vector<uint8_t> sortkeys;
  std::vector<Pt> sorted;

  int myrandom(int n);
  void set1(int r, int c, uint8_t v);
  void setbkgd(int r, int c, uint8_t v, bool f, bool dec);
  bool forceCells(int r, int c, int i, uint32_t e);
  bool consis9(int r, int c);
  bool proceed(int r, int c, uint8_t v, bool f, bool dec);
  bool backup();
  bool go(int r, int c, uint8_t v, bool f, int &wasfree);
  void listneighbors(int g);
  void changecurr(std::vector<uint8_t> &a, int g);
  uint8_t nxgen(int r, int c) const;
  void findchgcount(int g);
  bool trycell();
  bool computecellorbackup();
  int period() const;
  bool semifizzle() const;
  void readpattern(const PatternOp &op);
  void initarrays();
  void ensure(int n) { if ((int)chglist.size() <= n) chglist.resize(2 * n + 1024); }
  void fillcell(int mingen, int maxgen, int &minr, int &maxr, int &minc, int &maxc);
  void getrotordesc(int period, int minr, int maxr, int minc, int maxc,
                    int orientation, std::string &out) const;
};

}  // namespace drift
